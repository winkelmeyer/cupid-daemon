import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PACKAGE = "com.tinder"
ID = "com.tinder:id/"
DETAIL = ID + "sparksProfileDetailScrollView"
STACK = ID + "recs_cardstack"
NOISE_PREFIXES = ("Reply", "Photo of ", "Photo by ", "More options", "Share ", "Unmatch", "Block ", "Report ")
OUT_OF_LIKES = "(?i).*(out of likes|no daily cap|unlimited likes).*"
MATCH = "(?i).*it.s a match.*"
AD_MARKERS = re.compile(r"(?i)^(ad|sponsored|promoted|learn more|visit site|shop now|install|install now|download|sign up|get the app|book now|try double date\.?)$")
DISMISS = ["Close", "Close sheet", "Maybe later", "Not now", "No thanks", "No Thanks", "Skip"]
RUNS = Path(__file__).parent / "runs"


def screenshot(device, label):
    RUNS.mkdir(exist_ok=True)
    device.screenshot(str(RUNS / f"{datetime.now():%Y-%m-%d-%H%M%S}-tinder-{label}.png"))


def top_card(device):
    root = ET.fromstring(device.dump_hierarchy())
    stack = next((node for node in root.iter("node") if node.get("resource-id") == STACK), None)
    if stack is None:
        return None
    cards = [node for node in stack.iter("node") if node.get("class", "").endswith("CardView")]
    return max(cards, key=card_width, default=None)


def card_width(card):
    left, _, right, _ = map(int, card.get("bounds").replace("][", ",").strip("[]").split(","))
    return right - left


def card_key(card):
    headline = next((node for node in card.iter("node") if node.get("resource-id") == ID + "headline_view"), None)
    return (card.get("content-desc") or "", headline.get("content-desc") if headline is not None else "", tuple(card_texts(card)[:6]))


def card_texts(card):
    return [value for node in card.iter("node") for value in (node.get("text"), node.get("content-desc")) if value]


def is_ad(card):
    has_age = any(node.get("resource-id") == ID + "recs_card_user_headline_age" for node in card.iter("node"))
    paired = " & " in card_key(card)[1]
    return not has_age or paired or any(AD_MARKERS.search(text) for text in card_texts(card))


def card_label(card):
    names = [node.get("text") for node in card.iter("node") if node.get("resource-id") == ID + "recs_card_user_headline_name"]
    return (names[0] if names else card.get("content-desc") or "unknown card").rstrip(",").strip()


def on_deck(device):
    return device(resourceId=STACK).exists(timeout=3) and device(resourceId=ID + "gamepad_like").exists(timeout=1)


def dismiss_popups(device):
    for _ in range(5):
        if on_deck(device) and not device(resourceId=DETAIL).exists(timeout=1):
            return
        for label in DISMISS:
            button = device(description=label)
            if not button.exists:
                button = device(text=label)
            if button.exists:
                screenshot(device, f"popup-{label.replace(' ', '-').lower()}")
                button.click()
                time.sleep(2)
                break
        else:
            if device(resourceId=ID + "action_discovery").exists:
                device(resourceId=ID + "action_discovery").click()
                time.sleep(3)
            elif not device(packageName=PACKAGE).exists:
                device.app_start(PACKAGE)
                time.sleep(5)
            else:
                device.press("back")
                time.sleep(2)


def next_card(device):
    dismiss_popups(device)
    card = top_card(device)
    if card is None:
        return None
    return {"label": card_label(card), "ad": is_ad(card), "key": card_key(card)}


def detail_lines(device):
    root = ET.fromstring(device.dump_hierarchy())
    lines = []
    for node in root.iter("node"):
        if node.get("resource-id") != DETAIL:
            continue
        for child in node.iter("node"):
            text = re.sub(r"^\W+", "", child.get("text") or "")
            if len(text) > 1 and not text.startswith(NOISE_PREFIXES):
                lines.append(text)
    return lines


def read_profile(device):
    open_button = device(description="Open profile")
    if not open_button.exists(timeout=5):
        raise RuntimeError("no Open profile button on the top Tinder card")
    open_button[0].click()
    if not device(resourceId=DETAIL).exists(timeout=8):
        screenshot(device, "no-detail")
        raise RuntimeError("Tinder profile detail did not open")
    name = device(resourceId=ID + "recs_card_user_headline_name")[0].get_text().rstrip(",").strip()
    return name, read_open_detail(device)


def read_open_detail(device):
    lines = [device(resourceId=ID + "recs_card_user_headline_age")[0].get_text().strip()]
    for _ in range(8):
        for line in detail_lines(device):
            if line not in lines:
                lines.append(line)
        if not device(resourceId=DETAIL).scroll.forward(steps=40):
            break
        time.sleep(0.8)
    return lines


def act(device, button):
    before = top_card(device)
    before_key = card_key(before) if before is not None else None
    pads = device(resourceId=ID + button, className="android.widget.FrameLayout")
    if not pads.exists(timeout=5):
        raise RuntimeError(f"Tinder {button} button not found")
    pads[0].click()
    time.sleep(3)
    if device(textMatches=OUT_OF_LIKES).exists(timeout=2):
        device.press("back")
        return "out of likes"
    if device(textMatches=MATCH).exists(timeout=1):
        screenshot(device, "match")
        device.press("back")
        time.sleep(2)
        return "match"
    dismiss_popups(device)
    after = top_card(device)
    if after is not None and card_key(after) == before_key:
        screenshot(device, "stuck")
        raise RuntimeError(f"Tinder {button} did not move past {card_label(after)}")
    return "ok"


def like(device):
    return act(device, "gamepad_like")


def skip(device):
    return act(device, "gamepad_pass")
