#!/usr/bin/env python3
"""
send_email.py — Email today's jobwatch digest as a styled HTML message.

Reads the structured sidecar digest_YYYY-MM-DD.json that jobwatch.py writes,
then sends a clean two-section email (Senior roles and Other roles). Designed
to run in the GitHub Actions workflow after jobwatch.py. Standard library only.

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
SENIOR = "#4f46e5"   # indigo
OTHER = "#0d9488"    # teal
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,"
        "Arial,sans-serif")


def _loc(job):
    return job["location"] or ("Remote" if job["remote"] else "Location not listed")


def _role_html(job, accent):
    title = html.escape(job["title"])
    company = html.escape(job["company"])
    loc = html.escape(_loc(job))
    url = html.escape(job["url"], quote=True)
    return (
        f'<tr><td style="padding:14px 0;border-bottom:1px solid {BORDER};">'
        f'<a href="{url}" style="font:600 16px/1.35 {FONT};color:{accent};'
        f'text-decoration:none;">{title}</a>'
        f'<div style="font:400 13px/1.5 {FONT};color:{MUTED};margin-top:3px;">'
        f'{company} &middot; {loc}</div>'
        f'</td></tr>'
    )


def _section_html(label, group, accent):
    pill = (
        f'<span style="display:inline-block;background:{accent};color:#fff;'
        f'font:600 12px/1 {FONT};border-radius:999px;padding:5px 10px;'
        f'margin-left:8px;vertical-align:middle;">{len(group)}</span>'
    )
    header = (
        f'<tr><td style="padding:26px 0 6px;">'
        f'<span style="font:700 15px/1 {FONT};color:{INK};letter-spacing:.02em;'
        f'text-transform:uppercase;">{html.escape(label)}</span>{pill}'
        f'</td></tr>'
    )
    if group:
        rows = "".join(_role_html(j, accent) for j in group)
    else:
        rows = (f'<tr><td style="padding:12px 0;font:400 14px/1.5 {FONT};'
                f'color:{MUTED};">None today.</td></tr>')
    return header + rows


def build_html(today, seniors, others, warnings):
    total = len(seniors) + len(others)
    body = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{PAGE_BG};padding:24px 12px;">'
        f'<tr><td align="center">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;width:100%;background:{CARD_BG};border:1px solid '
        f'{BORDER};border-radius:14px;padding:28px 30px;">'
        # Header
        f'<tr><td style="font:700 22px/1.25 {FONT};color:{INK};">'
        f'New design roles</td></tr>'
        f'<tr><td style="font:400 14px/1.5 {FONT};color:{MUTED};padding-top:4px;">'
        f'{total} new for {html.escape(today)} '
        f'&nbsp;&middot;&nbsp; {len(seniors)} senior, {len(others)} other</td></tr>'
    )
    body += f'<tr><td>{_table(_section_html("Senior roles", seniors, SENIOR))}</td></tr>'
    body += f'<tr><td>{_table(_section_html("Other roles", others, OTHER))}</td></tr>'
    if warnings:
        warn_rows = "".join(
            f'<tr><td style="font:400 13px/1.5 {FONT};color:{MUTED};padding:4px 0;">'
            f'{html.escape(w)}</td></tr>' for w in warnings)
        body += (
            f'<tr><td style="padding:26px 0 6px;font:700 13px/1 {FONT};color:{MUTED};'
            f'text-transform:uppercase;">Warnings</td></tr>'
            f'<tr><td>{_table(warn_rows)}</td></tr>')
    body += (
        f'<tr><td style="padding-top:24px;font:400 12px/1.5 {FONT};color:{MUTED};">'
        f'Sent by jobwatch. Roles are de-duplicated, so each one appears once.'
        f'</td></tr>'
        f'</table></td></tr></table>'
    )
    return body


def _table(inner_rows):
    return (f'<table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0">{inner_rows}</table>')


def build_text(today, seniors, others, warnings):
    lines = [f"New design roles: {today}",
             f"{len(seniors) + len(others)} new "
             f"({len(seniors)} senior, {len(others)} other)", ""]
    for label, group in (("Senior roles", seniors), ("Other roles", others)):
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
    seniors = digest.get("seniors", [])
    others = digest.get("others", [])
    warnings = digest.get("warnings", [])

    total = len(seniors) + len(others)
    if total == 0:
        print("No new matches today. Skipping email.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"{total} new design role(s): {today}"
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(build_text(today, seniors, others, warnings))
    msg.add_alternative(build_html(today, seniors, others, warnings), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, app_pw)
        server.send_message(msg)
    print(f"Emailed {total} match(es) ({len(seniors)} senior, {len(others)} other) "
          f"to {to_addr}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Never fail the workflow because of email trouble.
        print(f"Email step error (non-fatal): {e}", file=sys.stderr)
