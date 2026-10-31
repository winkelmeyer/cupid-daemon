import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path

CHAT_DB = Path.home() / "Library/Messages/chat.db"
APPLE_EPOCH = 978307200
COMMAND = re.compile(r"^\s*([yne])(\d+)\s*(.*)$", re.IGNORECASE | re.DOTALL)


def send(text):
    handle = os.environ["IMESSAGE_TO"]
    script = (
        'on run argv\n'
        'tell application "Messages"\n'
        'set svc to 1st account whose service type = iMessage\n'
        'send (item 1 of argv) to participant (item 2 of argv) of svc\n'
        'end tell\n'
        'end run'
    )
    subprocess.run(["osascript", "-e", script, text, handle], check=True)


def decode_body(text, attributed_body):
    if text:
        return text
    if not attributed_body or b"NSString" not in attributed_body:
        return ""
    body = attributed_body.split(b"NSString", 1)[1][5:]
    if body[0] == 0x81:
        length = int.from_bytes(body[1:3], "little")
        return body[3:3 + length].decode("utf-8", "ignore")
    return body[1:1 + body[0]].decode("utf-8", "ignore")


def commands_since(since_unix):
    since_apple_ns = int((since_unix - APPLE_EPOCH) * 1e9)
    with sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True) as db:
        rows = db.execute(
            "select text, attributedBody from message where date > ? order by date",
            (since_apple_ns,),
        ).fetchall()
    commands = []
    for text, attributed_body in rows:
        match = COMMAND.match(decode_body(text, attributed_body))
        if match:
            commands.append((match.group(1).lower(), int(match.group(2)), match.group(3).strip()))
    return commands


def wait_for_decisions(ids, window_s, poll_s=30):
    started = time.time()
    decisions = {}
    while time.time() - started < window_s and len(decisions) < len(ids):
        for verb, number, text in commands_since(started):
            if number in ids and number not in decisions:
                decisions[number] = (verb, text)
        time.sleep(poll_s)
    return decisions
