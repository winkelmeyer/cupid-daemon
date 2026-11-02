import email
import email.policy
import email.utils
import imaplib
import os
import re
import smtplib
import subprocess
import time
from email.message import EmailMessage

SUBJECT = "[cupid-daemon]"
COMMAND = re.compile(r"^\s*([yne])(\d+)\s*(.*)$", re.IGNORECASE)


def credentials():
    user = os.environ["MAIL_USER"]
    password = subprocess.run(
        ["security", "find-generic-password", "-s", "cupid-daemon-mail", "-w"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return user, password


def send(text):
    user, password = credentials()
    message = EmailMessage()
    message["From"] = user
    message["To"] = os.environ["MAIL_TO"]
    message["Subject"] = f"{SUBJECT} {text.splitlines()[0]}"
    message.set_content(text)
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), 465, timeout=10) as smtp:
        smtp.login(user, password)
        smtp.send_message(message)


def first_reply_line(message):
    part = message.get_body(preferencelist=("plain",)) if message.is_multipart() else message
    body = part.get_content() if hasattr(part, "get_content") else part.get_payload(decode=True).decode()
    for line in body.splitlines():
        if line.strip() and not line.startswith(">"):
            return line.strip()
    return ""


def commands_since(since_unix):
    user, password = credentials()
    since = time.strftime("%d-%b-%Y", time.gmtime(since_unix))
    commands = []
    with imaplib.IMAP4_SSL(os.environ.get("IMAP_HOST", "imap.gmail.com"), timeout=10) as imap:
        imap.login(user, password)
        imap.select("INBOX")
        _, ids = imap.search(None, f'(SINCE {since} SUBJECT "{SUBJECT}")')
        for message_id in ids[0].split():
            _, data = imap.fetch(message_id, "(RFC822)")
            message = email.message_from_bytes(data[0][1], policy=email.policy.default)
            if user.lower() in (message["From"] or "").lower():
                continue
            sent = email.utils.parsedate_to_datetime(message["Date"]).timestamp()
            match = COMMAND.match(first_reply_line(message)) if sent >= since_unix else None
            if match:
                commands.append((match.group(1).lower(), int(match.group(2)), match.group(3).strip()))
    return commands


def wait_for_decisions(ids, window_s, poll_s=60):
    started = time.time()
    decisions = {}
    while time.time() - started < window_s and len(decisions) < len(ids):
        for verb, number, text in commands_since(started):
            if number in ids and number not in decisions:
                decisions[number] = (verb, text)
        time.sleep(poll_s)
    return decisions
