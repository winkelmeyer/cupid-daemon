import re
import xml.etree.ElementTree as ET

from llm import create_client
import uiautomator2 as u2

MODEL = "claude-sonnet-5-5"
STYLE = "casual, short, a bit playful, asks one concrete question, no emojis spam, no pickup lines"


def visible_chat_text(device):
    root = ET.fromstring(device.dump_hierarchy())
    texts = [n.get("text") for n in root.iter("node") if n.get("text")]
    return "\n".join(t for t in texts if len(t) > 1)


def suggest(chat):
    client = create_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": (
                f"This is the visible text of a dating-app chat screen:\n\n{chat}\n\n"
                f"Suggest 3 different next messages from me. Style: {STYLE}. "
                "Return them as a numbered list, one line each, nothing else."
            ),
        }],
    )
    lines = response.content[0].text.strip().splitlines()
    return [re.sub(r"^\d+[.)]\s*", "", line).strip() for line in lines if line.strip()][:3]


def send(device, message):
    field = device(className="android.widget.EditText")
    if not field.exists(timeout=3):
        raise RuntimeError("no message input field on screen; open a chat first")
    field.set_text(message)
    device(descriptionMatches="(?i)send").click()


def main():
    device = u2.connect()
    while True:
        input("\nOpen a chat on the phone, then press Enter (Ctrl+C to quit)...")
        options = suggest(visible_chat_text(device))
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        choice = input("Pick 1-3, type your own message, or leave empty to skip: ").strip()
        if not choice:
            continue
        message = options[int(choice) - 1] if choice in {"1", "2", "3"} else choice
        if input(f"Send \"{message}\"? [y/N] ").strip().lower() == "y":
            send(device, message)
            print("sent")


if __name__ == "__main__":
    main()
