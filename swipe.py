import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import subprocess
import xml.etree.ElementTree as ET

import uiautomator2 as u2

from comments import write_comment

APPS = {
    "hinge": {
        "package": "co.hinge.app",
        "like": {"description": "Like photo"},
        "skip": {"descriptionStartsWith": "Skip "},
    },
    "bumble": {
        "package": "com.bumble.app",
        "like": None,
        "skip": None,
    },
}

DAILY_LIMIT = 40
MIN_DELAY_S = 4
MAX_DELAY_S = 14
MAX_AGE = 45
SKIP_IF_PRESENT = {"Have children", "Life partner", "Long-term relationship"}
LOG = Path(__file__).parent / "swipe.log"
RUNS = Path(__file__).parent / "runs"
OUT_OF_LIKES = "You're out of free likes for today"


def log(line):
    stamped = f"{datetime.now().isoformat(timespec='seconds')} {line}"
    print(stamped)
    with LOG.open("a") as f:
        f.write(stamped + "\n")


def dump(device, app):
    device.app_start(APPS[app]["package"])
    time.sleep(4)
    out = Path(__file__).parent / f"{app}-ui.xml"
    out.write_text(device.dump_hierarchy())
    device.screenshot(str(out.with_suffix(".png")))
    print(f"wrote {out} and {out.with_suffix('.png')}")


def tap(device, selector):
    element = device(**selector)
    if not element.exists(timeout=5):
        raise RuntimeError(f"selector not found on screen: {selector}")
    element.click()


def read_profile(device):
    lines = []
    for _ in range(6):
        for node in ET.fromstring(device.dump_hierarchy()).iter("node"):
            text = node.get("text") or ""
            desc = node.get("content-desc") or ""
            field = desc if desc.startswith(("Prompt:", "Poll")) else text
            if len(field) > 1 and field not in lines:
                lines.append(field)
        device.shell("input swipe 540 1800 540 900 300")
        time.sleep(1)
    for _ in range(3):
        device.shell("input swipe 540 600 540 2000 100")
    time.sleep(1)
    return lines


def rule_verdict(lines):
    ages = [int(line) for line in lines if line.isdigit() and 18 <= int(line) <= 99]
    if not ages:
        return None
    if ages[0] > MAX_AGE:
        return f"age {ages[0]}"
    hits = SKIP_IF_PRESENT.intersection(lines)
    if hits:
        return ", ".join(sorted(hits))
    return None


def ask_human(device, name):
    shot = Path(__file__).parent / "current.png"
    device.screenshot(str(shot))
    subprocess.run(["open", str(shot)])
    answer = input(f"{name}: [l]ike / [s]kip / [q]uit? ").strip().lower()
    return {"l": "like", "s": "skip", "q": "quit"}.get(answer, "skip")


def type_slowly(device, text):
    for char in text:
        escaped = "%s" if char == " " else char.replace("'", "'\\''")
        device.shell(f"input text '{escaped}'")
        time.sleep(random.uniform(0.08, 0.3))


def send_like(device, config, comment):
    tap(device, config["like"])
    if not device(description="Edit comment").exists(timeout=5):
        raise RuntimeError("like dialog did not open")
    device(description="Edit comment").click()
    time.sleep(1)
    type_slowly(device, comment)
    time.sleep(random.uniform(1.5, 3))
    if not device(description="Send like with message").exists(timeout=2):
        device.press("back")
    device(description="Send like with message").click()
    anyway = device(text="Send Like anyway")
    if anyway.exists(timeout=3):
        anyway.click()


def out_of_likes(device):
    if not device(text=OUT_OF_LIKES).exists(timeout=3):
        return False
    device(description="Close").click()
    return True


def write_report(app, rows):
    RUNS.mkdir(exist_ok=True)
    report = RUNS / f"{datetime.now():%Y-%m-%d-%H%M}-{app}.md"
    likes = sum(1 for row in rows if row[2].startswith("like"))
    lines = [
        f"# {app} run {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"{len(rows)} profiles, {likes} likes, {len(rows) - likes} skips",
        "",
        "| Time | Profile | Action | Reason / comment |",
        "|---|---|---|---|",
    ] + [f"| {t} | {name} | {action} | {detail} |" for t, name, action, detail in rows]
    report.write_text("\n".join(lines) + "\n")
    log(f"report written to {report}")


def swipe(device, app, count, auto):
    config = APPS[app]
    if not config["like"] or not config["skip"]:
        raise RuntimeError(f"{app} selectors not configured yet; run `dump {app}` first")
    device.app_start(config["package"])
    time.sleep(5)
    rows = []
    try:
        for _ in range(count):
            skip_button = device(**config["skip"])
            if not skip_button.exists(timeout=5):
                raise RuntimeError("no profile on screen")
            name = skip_button.info["contentDescription"].removeprefix("Skip ")
            lines = read_profile(device)
            reason = rule_verdict(lines)
            action = "skip" if reason else ("like" if auto else ask_human(device, name))
            if action == "quit":
                break
            now = f"{datetime.now():%H:%M}"
            if action == "skip":
                tap(device, config["skip"])
                rows.append((now, name, "skip", f"rule: {reason}" if reason else "manual"))
                log(f"{app} {name} skip" + (f" (rule: {reason})" if reason else ""))
            else:
                comment = write_comment(lines)
                send_like(device, config, comment)
                if out_of_likes(device):
                    rows.append((now, name, "like UNCONFIRMED (limit hit)", comment))
                    log(f"{app} {name} like UNCONFIRMED, out of likes: {comment}")
                    break
                rows.append((now, name, "like + comment", comment))
                log(f"{app} {name} like + comment: {comment}")
            time.sleep(random.uniform(MIN_DELAY_S, MAX_DELAY_S))
    finally:
        write_report(app, rows)


def main():
    command, app = sys.argv[1], sys.argv[2]
    device = u2.connect(os.environ.get("PHONE_ADB"))
    if command == "dump":
        dump(device, app)
    elif command == "swipe":
        count = min(int(sys.argv[3]) if len(sys.argv) > 3 else 20, DAILY_LIMIT)
        swipe(device, app, count, "--auto" in sys.argv)
    else:
        raise SystemExit("usage: swipe.py dump|swipe <hinge|bumble> [count]")


if __name__ == "__main__":
    main()
