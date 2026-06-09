#!/usr/bin/env python3
"""
send_email.py — Email today's jobwatch digest as a styled HTML message.

Reads the structured sidecar digest_YYYY-MM-DD.json that jobwatch.py writes,
then sends a clean two-section email: Roles first (titles that do not say
senior), then Senior roles. Boston-area and remote roles are sorted to the top
of each section by jobwatch.py. Standard library only.

It sends ONLY when there are new matches, so you do not get a daily empty email.

Configuration comes from environment variables (set as GitHub repo secrets):
  GMAIL_USER          the Gmail address you send FROM (also the SMTP login)
  GMAIL_APP_PASSWORD  a Google "app password" (NOT your normal password)
  MAIL_TO             where to send the digest (defaults to GMAIL_USER)

If GMAIL_USER or GMAIL_APP_PASSWORD is missing, the script exits quietly so the
workflow does not fail. Set the two secrets to turn email on.
"""

import html
import json
import os
import smtplib
import sys
from datetime import date
from email.message import EmailMessage

# Color and type tokens (inline styles, since email clients ignore <style>).
INK = "#1f2330"
MUTED = "#6b7280"
PAGE_BG = "#f4f5f7"
CARD_BG = "#ffffff"
BORDER = "#e8eaed"
BLUE = "#2563eb"     # "Roles" section
GREY = "#6b7280"     # "Senior roles" section
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,"
        "Arial,sans-serif")

# Hosted "Open all" page (GitHub Pages). Override with MAIL_OPEN_ALL_URL.
OPEN_ALL_URL = os.environ.get("MAIL_OPEN_ALL_URL", "").strip() or \
    "https://c-huitt.github.io/jobwatch/"


def pretty_date(iso):
    d = date.fromisoformat(iso)
    n = d.day
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{d.strftime('%B')} {n}{suffix} {d.year}"


def _loc(job):
    return job["location"] or ("Remote" if job["remote"] else "Location not listed")


def _role_html(job, accent):
    title = html.escape(job["title"])
    company = html.escape(job["company"])
    loc = html.escape(_loc(job))
    url = html.escape(job["url"], quote=True)
    return (
        f'<tr><td style="padding:20px 0;border-bottom:1px solid {BORDER};">'
        f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
        f'style="font:600 16px/1.4 {FONT};color:{accent};text-decoration:none;">'
        f'{title}</a>'
        f'<div style="font:400 13px/1.6 {FONT};color:{MUTED};margin-top:5px;">'
        f'{company} &middot; {loc}</div>'
        f'</td></tr>'
    )


def _section_html(label, group, accent):
    pill = (
        f'<span style="display:inline-block;background:{accent};color:#fff;'
        f'font:600 12px/1 {FONT};border-radius:999px;padding:5px 11px;'
        f'margin-left:10px;vertical-align:middle;">{len(group)}</span>'
    )
    header = (
        f'<tr><td style="padding:38px 0 8px;">'
        f'<span style="font:700 15px/1 {FONT};color:{INK};letter-spacing:.03em;'
        f'text-transform:uppercase;">{html.escape(label)}</span>{pill}'
        f'</td></tr>'
    )
    if group:
        rows = "".join(_role_html(j, accent) for j in group)
    else:
        rows = (f'<tr><td style="padding:16px 0;font:400 14px/1.6 {FONT};'
                f'color:{MUTED};">None today.</td></tr>')
    return header + rows


def _table(inner_rows):
    return (f'<table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0">{inner_rows}</table>')


def build_html(today, others, seniors, warnings):
    total = len(others) + len(seniors)
    body = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{PAGE_BG};padding:32px 12px;">'
        f'<tr><td align="center">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;width:100%;background:{CARD_BG};border:1px solid '
        f'{BORDER};border-radius:14px;padding:36px 38px;">'
        # Header
        f'<tr><td style="font:700 23px/1.3 {FONT};color:{INK};">'
        f'New design roles</td></tr>'
        f'<tr><td style="font:400 14px/1.6 {FONT};color:{MUTED};padding-top:6px;">'
        f'{total} new for {html.escape(pretty_date(today))} '
        f'&nbsp;&middot;&nbsp; {len(others)} roles, {len(seniors)} senior</td></tr>'
        # Open-all button
        f'<tr><td style="padding-top:18px;">'
        f'<a href="{html.escape(OPEN_ALL_URL, quote=True)}" target="_blank" '
        f'rel="noopener" style="display:inline-block;background:{BLUE};color:#fff;'
        f'font:600 14px/1 {FONT};text-decoration:none;padding:13px 22px;'
        f'border-radius:10px;">Open all {total} in your browser &#8599;</a></td></tr>'
    )
    body += f'<tr><td>{_table(_section_html("Roles", others, BLUE))}</td></tr>'
    body += f'<tr><td>{_table(_section_html("Senior roles", seniors, GREY))}</td></tr>'
    if warnings:
        warn_rows = "".join(
            f'<tr><td style="font:400 13px/1.6 {FONT};color:{MUTED};padding:5px 0;">'
            f'{html.escape(w)}</td></tr>' for w in warnings)
        body += (
            f'<tr><td style="padding:38px 0 8px;font:700 13px/1 {FONT};color:{MUTED};'
            f'text-transform:uppercase;">Warnings</td></tr>'
            f'<tr><td>{_table(warn_rows)}</td></tr>')
    body += (
        f'<tr><td style="padding-top:32px;font:400 12px/1.6 {FONT};color:{MUTED};">'
        f'Sent by jobwatch. Roles are de-duplicated, so each one appears once.'
        f'</td></tr>'
        f'</table></td></tr></table>'
    )
    return body


def build_text(today, others, seniors, warnings):
    lines = [f"New design roles: {pretty_date(today)}",
             f"{len(others) + len(seniors)} new "
             f"({len(others)} roles, {len(seniors)} senior)", ""]
    for label, group in (("Roles", others), ("Senior roles", seniors)):
        lines.append(f"{label} ({len(group)})")
        if group:
            for j in group:
                lines.append(f"  - {j['title']} - {j['company']} ({_loc(j)})")
                lines.append(f"    {j['url']}")
        else:
            lines.append("  None today.")
        lines.append("")
    if warnings:
        lines.append("Warnings")
        lines += [f"  - {w}" for w in warnings]
    return "\n".join(lines)


def main():
    user = os.environ.get("GMAIL_USER", "").strip()
    app_pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not user or not app_pw:
        print("Email not configured (GMAIL_USER / GMAIL_APP_PASSWORD unset). Skipping.")
        return

    to_addr = os.environ.get("MAIL_TO", "").strip() or user

    today = date.today().isoformat()
    path = f"digest_{today}.json"
    if not os.path.exists(path):
        print(f"No digest file {path} found. Skipping email.")
        return

    with open(path, "r", encoding="utf-8") as f:
        digest = json.load(f)
    others = digest.get("others", [])
    seniors = digest.get("seniors", [])
    warnings = digest.get("warnings", [])

    total = len(others) + len(seniors)
    if total == 0:
        print("No new matches today. Skipping email.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"{total} new design role(s): {pretty_date(today)}"
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(build_text(today, others, seniors, warnings))
    msg.add_alternative(build_html(today, others, seniors, warnings), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, app_pw)
        server.send_message(msg)
    print(f"Emailed {total} match(es) ({len(others)} roles, {len(seniors)} senior) "
          f"to {to_addr}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Never fail the workflow because of email trouble.
        print(f"Email step error (non-fatal): {e}", file=sys.stderr)
