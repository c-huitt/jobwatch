#!/usr/bin/env python3
"""
notify_failure.py — Email an alert when a jobwatch run fails.

Run by the GitHub Actions workflow only on failure (if: failure()). Sends a
short plain-text email with a link to the failed run so you can investigate.
Standard library only. Exits quietly if the Gmail secrets are not set.

Environment:
  GMAIL_USER, GMAIL_APP_PASSWORD  Gmail SMTP login (repo secrets)
  MAIL_TO                         recipient (defaults to GMAIL_USER)
  RUN_URL                         link to the failed workflow run
"""

import os
import smtplib
from datetime import date
from email.message import EmailMessage


def main():
    user = os.environ.get("GMAIL_USER", "").strip()
    app_pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not user or not app_pw:
        print("Email not configured. Cannot send failure alert.")
        return
    to_addr = os.environ.get("MAIL_TO", "").strip() or user
    run_url = os.environ.get("RUN_URL", "").strip() or "(no run URL provided)"

    msg = EmailMessage()
    msg["Subject"] = f"jobwatch FAILED: {date.today().isoformat()}"
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(
        "A jobwatch run failed today.\n\n"
        f"Check the run log here:\n{run_url}\n\n"
        "No digest could be produced for this run. The next scheduled run will "
        "try again automatically."
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, app_pw)
        server.send_message(msg)
    print(f"Failure alert sent to {to_addr}.")


if __name__ == "__main__":
    main()
