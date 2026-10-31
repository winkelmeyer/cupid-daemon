import time
import xml.etree.ElementTree as ET

from swipe import type_slowly

SCREEN_MID_X = 540
YOUR_TURN = "Your turn"


def open_matches(device):
    device(description="Matches").click()
    time.sleep(3)


def list_your_turn_chats(device):
    open_matches(device)
    nodes = list(ET.fromstring(device.dump_hierarchy()).iter("node"))
    names = []
    for index, node in enumerate(nodes):
        if (node.get("text") or "") == YOUR_TURN:
            for previous in reversed(nodes[max(0, index - 6):index]):
                text = previous.get("text") or ""
                if len(text) > 1 and text != YOUR_TURN:
                    names.append(text)
                    break
    return names


def open_chat(device, name):
    open_matches(device)
    row = device(text=name)
    if not row.exists(timeout=5):
        raise RuntimeError(f"chat with {name} not found in Matches")
    row.click()
    time.sleep(3)


def bounds_center_x(bounds):
    left = int(bounds.split("][")[0].strip("[").split(",")[0])
    right = int(bounds.split("][")[1].strip("]").split(",")[0])
    return (left + right) // 2


def read_open_chat(device):
    lines = []
    for node in ET.fromstring(device.dump_hierarchy()).iter("node"):
        text = node.get("text") or ""
        if len(text) < 2 or node.get("class") == "android.widget.EditText":
            continue
        side = "me" if bounds_center_x(node.get("bounds")) > SCREEN_MID_X else "her"
        lines.append(f"{side}: {text}")
    return lines


def send_in_open_chat(device, message):
    field = device(className="android.widget.EditText")
    if not field.exists(timeout=5):
        raise RuntimeError("no message field in the open chat")
    field.click()
    time.sleep(1)
    type_slowly(device, message)
    time.sleep(1)
    send = device(descriptionMatches="(?i)^send$")
    if not send.exists(timeout=3):
        send = device(textMatches="(?i)^send$")
    if not send.exists(timeout=3):
        raise RuntimeError("no Send button in the open chat")
    send.click()
