"""The two ways this app talks to the outside world.

Both use only the Python standard library, which the project spec requires:

* send_email -- smtplib if MAIL_SERVER is set in config.py, otherwise the
  message is written into instance/outbox/ as a .eml file. That default lets
  the Celery jobs be demonstrated without running an SMTP server.
* send_gchat -- one HTTP POST to a Google Chat webhook via urllib.

Neither function raises. A batch job mails a whole list of people, so one bad
address or a webhook that is down must not stop the rest of the run; the
caller gets False instead of an exception.
"""

import json
import smtplib
import urllib.request
from datetime import datetime
from email.message import EmailMessage

from .config import Config


def send_email(to, subject, html_body):
    """Send one HTML e-mail. Returns True on success, False on failure."""
    message = EmailMessage()
    message["From"] = Config.MAIL_SENDER
    message["To"] = to
    message["Subject"] = subject
    message.set_content("Open this message in an HTML capable mail reader.")
    message.add_alternative(html_body, subtype="html")

    try:
        if not Config.MAIL_SERVER:
            return _write_to_outbox(message, to)

        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=20) as smtp:
            smtp.starttls()
            if Config.MAIL_USERNAME:
                smtp.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            smtp.send_message(message)
        print(f"[mailer] sent '{subject}' to {to}")
        return True
    except Exception as error:
        print(f"[mailer] could not send to {to}: {error}")
        return False


def _write_to_outbox(message, to):
    """Save the message as a file instead of sending it."""
    Config.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    # Microseconds in the name so a batch of mails cannot overwrite each other.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe_address = to.replace("@", "_at_").replace("/", "_")
    path = Config.OUTBOX_DIR / f"{stamp}-{safe_address}.eml"
    path.write_text(message.as_string(), encoding="utf-8")
    print(f"[mailer] wrote {path}")
    return True


def send_gchat(text):
    """Post a plain text message to the Google Chat webhook.

    Returns False when no webhook is configured, which is how the reminder job
    knows to fall back to e-mail.
    """
    if not Config.GCHAT_WEBHOOK_URL:
        return False

    body = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        Config.GCHAT_WEBHOOK_URL,
        data=body,
        headers={"Content-Type": "application/json; charset=UTF-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status == 200
    except Exception as error:
        print(f"[mailer] google chat post failed: {error}")
        return False
