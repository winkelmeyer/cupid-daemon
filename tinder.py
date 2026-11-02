import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PACKAGE = "com.tinder"
ID = "com.tinder:id/"
DETAIL = ID + "sparksProfileDetailScrollView"
NOISE_PREFIXES = ("Reply", "Photo of ", "Photo by ", "More options")
OUT_OF_LIKES = "(?i).*out of likes.*"
MATCH = "(?i).*it.s a match.*"
RUNS = Path(__file__).parent / "runs"


DISMISS = ["Close", "Close sheet", "Maybe later", "Not now", "No thanks", "No Thanks", "Skip"]


def dismiss_popups(device):
    for _ in range(4):
        if device(resourceId=ID + "recs_card_user_headline_name").exists(timeout=3):
            return
        for label in DISMISS:
            button = device(description=label)
            if not button.exists:
                button = device(text=label)
            if button.exists:
                log_popup(device, label)
                button.click()
                time.sleep(2)
                break
        else:
            if device.app_current()["package"] != PACKAGE:
                device.app_start(PACKAGE)
                time.sleep(5)
            else:
                device.press("back")
                time.sleep(2)


def log_popup(device, label):
    RUNS.mkdir(exist_ok=True)
    device.screenshot(str(RUNS / f"{datetime.now():%Y-%m-%d-%H%M%S}-tinder-popup-{label.replace(' ', '-').lower()}.png"))


def top_card_name(device):
    dismiss_popups(device)
    names = device(resourceId=ID + "recs_card_user_headline_name")
    if not names.exists(timeout=5):
        return None
    return names[0].get_text().rstrip(",").strip()


def detail_lines(device):
    root = ET.fromstring(device.dump_hierarchy())
    lines = []
    for node in root.iter("node"):
        if node.get("resource-id") != DETAIL:
            continue
        for child in node.iter("node"):
            text = child.get("text") or ""
            text = re.sub(r"^\W+", "", text)
            if len(text) > 1 and not text.startswith(NOISE_PREFIXES):
                lines.append(text)
    return lines


def read_profile(device):
    open_button = device(description="Open profile")
    if not open_button.exists(timeout=5):
        raise RuntimeError("no Tinder profile card on screen")
    open_button[0].click()
    if not device(resourceId=DETAIL).exists(timeout=8):
        raise RuntimeError("Tinder profile detail did not open")
    name = device(resourceId=ID + "recs_card_user_headline_name")[0].get_text().rstrip(",").strip()
    age = device(resourceId=ID + "recs_card_user_headline_age")[0].get_text().strip()
    lines = [age]
    for _ in range(8):
        for line in detail_lines(device):
            if line not in lines:
                lines.append(line)
        if not device(resourceId=DETAIL).scroll.forward(steps=40):
            break
        time.sleep(0.8)
    return name, lines


def act(device, button):
    before = device(resourceId=ID + "recs_card_user_headline_name")[0].get_text().rstrip(",").strip()
    pads = device(resourceId=ID + button, className="android.widget.FrameLayout")
    if not pads.exists(timeout=5):
        raise RuntimeError(f"Tinder {button} button not found")
    pads[0].click()
    time.sleep(3)
    if device(textMatches=OUT_OF_LIKES).exists(timeout=2):
        device.press("back")
        return "out of likes"
    if device(textMatches=MATCH).exists(timeout=1):
        device.screenshot(str(RUNS / f"{datetime.now():%Y-%m-%d-%H%M%S}-tinder-match.png"))
        device.press("back")
        time.sleep(2)
        return "match"
    if top_card_name(device) == before and device(resourceId=DETAIL).exists(timeout=1):
        device.screenshot(str(RUNS / f"{datetime.now():%Y-%m-%d-%H%M%S}-tinder-stuck.png"))
        raise RuntimeError(f"Tinder {button} did not move past {before}")
    return "ok"


def like(device):
    return act(device, "gamepad_like")


def skip(device):
    return act(device, "gamepad_pass")
