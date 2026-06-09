#!/usr/bin/env python3
"""
send_email.py — Email today's jobwatch digest.

Reads new_jobs_YYYY-MM-DD.md for today and emails it. Designed to run in the
GitHub Actions workflow after jobwatch.py. Uses only the standard library.

It sends ONLY when there are new matches, so you do not get a daily empty email.

Configuration comes from environment variables (set as GitHub repo secrets):
  GMAIL_USER          the Gmail address you send FROM (also the SMTP login)
  GMAIL_APP_PASSWORD  a Google "app password" (NOT your normal password)
  MAIL_TO             where to send the digest (defaults to GMAIL_USER)

If GMAIL_USER or GMAIL_APP_PASSWORD is missing, the script exits quietly so the
workflow does not fail. Set the two secrets to turn email on.
"""

import os
import smtplib
import sys
from datetime import date
from email.message import EmailMessage


def main():
    user = os.environ.get("GMAIL_USER", "").strip()
    app_pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not user or not app_pw:
        print("Email not configured (GMAIL_USER / GMAIL_APP_PASSWORD unset). Skipping.")
        return

    to_addr = os.environ.get("MAIL_TO", "").strip() or user

    today = date.today().isoformat()
    path = f"new_jobs_{today}.md"
    if not os.path.exists(path):
        print(f"No digest file {path} found. Skipping email.")
        return

    with open(path, "r", encoding="utf-8") as f:
        body = f.read()

    # Count matches: each match is a bullet that starts with "- **".
    match_count = sum(1 for line in body.splitlines() if line.startswith("- **"))
    if match_count == 0:
        print("No new matches today. Skipping email.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"{match_count} new design role(s) - {today}"
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, app_pw)
        server.send_message(msg)
    print(f"Emailed {match_count} match(es) to {to_addr}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Never fail the workflow because of email trouble.
        print(f"Email step error (non-fatal): {e}", file=sys.stderr)
