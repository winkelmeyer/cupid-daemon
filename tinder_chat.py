import time
import xml.etree.ElementTree as ET

import tinder
from hinge_chat import bounds_center_x
from swipe import type_slowly

ID = tinder.ID
SCREEN_MID_X = 540
INPUT = ID + "textMessageInput"


def open_matches(device):
    if device(description="Exit chat").exists:
        device(description="Exit chat").click()
        time.sleep(2)
    for _ in range(3):
        if device(resourceId=ID + "action_matches").exists(timeout=3):
            break
        tinder.screenshot(device, "chat-popup")
        device.press("back")
        time.sleep(2)
    device(resourceId=ID + "action_matches").click()
    time.sleep(3)
    if not device(resourceId=ID + "matchesSearchBar").exists(timeout=5):
        raise RuntimeError("Tinder Chat tab did not open")


def list_chats(device):
    open_matches(device)
    nodes = list(ET.fromstring(device.dump_hierarchy()).iter("node"))
    new_matches = [node.get("text") for node in nodes if node.get("resource-id") == ID + "matchName" and node.get("class").endswith("TextView") and is_new_match(nodes, node)]
    your_turn = []
    for row in nodes:
        if row.get("resource-id") != ID + "matchRowView":
            continue
        texts = {child.get("resource-id"): child.get("text") for child in row.iter("node")}
        if (texts.get(ID + "trailingLabelText") or "").lower() == "your turn":
            your_turn.append(texts[ID + "matchName"])
    return [(name, "new match, no messages yet") for name in new_matches] + [(name, "her turn is done, your turn") for name in your_turn]


def is_new_match(nodes, name_node):
    return any(node.get("resource-id") == ID + "newMatchAvatarAndNameContainer" and name_node in list(node.iter("node")) for node in nodes)


def open_chat(device, name):
    open_matches(device)
    row = device(resourceId=ID + "matchName", text=name)
    if not row.exists(timeout=5):
        raise RuntimeError(f"Tinder chat with {name} not found")
    row.click()
    time.sleep(3)
    if not device(resourceId=INPUT).exists(timeout=5):
        raise RuntimeError(f"Tinder chat with {name} did not open")


def read_open_chat(device):
    lines = []
    for node in ET.fromstring(device.dump_hierarchy()).iter("node"):
        if node.get("resource-id") == ID + "chatTextMessageContent":
            side = "me" if bounds_center_x(node.get("bounds")) > SCREEN_MID_X else "her"
            lines.append(f"{side}: {node.get('text').strip()}")
    return lines


def read_match_profile(device):
    device(resourceId=ID + "avatarView").click()
    if not device(resourceId=tinder.DETAIL).exists(timeout=8):
        raise RuntimeError("Tinder match profile did not open")
    lines = tinder.read_open_detail(device)
    device.press("back")
    time.sleep(2)
    if not device(resourceId=INPUT).exists(timeout=5):
        raise RuntimeError("did not return to the Tinder chat after reading the profile")
    return lines


def send_in_open_chat(device, message):
    device(resourceId=INPUT).click()
    time.sleep(1)
    type_slowly(device, message)
    time.sleep(1)
    if device(resourceId=INPUT).get_text() != message:
        raise RuntimeError("typed Tinder message does not match the approved text")
    device(resourceId=ID + "textMessageSendButton").click()
    time.sleep(2)


def unmatch_open_chat(device, name):
    device(description="Safety Toolkit").click()
    time.sleep(2)
    device(text=f"Unmatch from {name}").click()
    time.sleep(2)
    confirm = device(textMatches="(?i)^(yes, )?unmatch$")
    if not confirm.exists(timeout=5):
        tinder.screenshot(device, "unmatch-no-confirm")
        raise RuntimeError(f"no Unmatch confirmation for {name}")
    confirm.click()
    time.sleep(3)
