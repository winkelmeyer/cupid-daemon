import argparse
import os
import random
import time
from datetime import datetime
from pathlib import Path

import xml.etree.ElementTree as ET

import uiautomator2 as u2
from anthropic import beta_tool

import mail as approvals
import tinder
import tinder_chat
from llm import create_client
from hinge_chat import list_your_turn_chats, open_chat, read_open_chat, send_in_open_chat
from swipe import APPS, log, out_of_likes, read_profile, rule_verdict, send_like, tap, type_slowly, write_report

MODEL = "claude-opus-5-5"
MAX_PROFILES = 40
APPROVAL_WINDOW_S = 3 * 60 * 60
HERE = Path(__file__).parent
HINGE = APPS["hinge"]
INCOMING = {
    "tab": {"descriptionStartsWith": "Likes You"},
    "card": {"descriptionContains": " liked your"},
    "match": {"descriptionStartsWith": "Match with "},
    "skip": {"description": "Skip"},
}
MAX_INCOMING = 20

device = None
rows = []
proposals = {}
unmatches = {}
state = {"current": None, "seen": 0, "likes_left": True, "incoming_seen": 0, "app": "hinge"}

SYSTEM = f"""You run Daniel's Hinge account for one daily session. Persona and voice:

{(HERE / "persona.md").read_text()}

Session plan:
1. Call next_profile repeatedly. Hard rules are already enforced by the tool. For each profile it returns,
   decide like or skip from Daniel's preferences, then call like_with_comment or skip_profile.
   A like always carries a comment that hooks on something specific in her profile, in Daniel's voice,
   one or two sentences, only facts from the persona.
2. Stop liking when a tool reports no likes left or no more profiles.
3. Call next_incoming_like repeatedly. These people already liked Daniel. Hard rules are enforced by the tool.
   Decide from Daniel's preferences: match_incoming (with a comment, same rules as a like) or skip_incoming. Stop when it
   reports none left.
4. Call list_chats. For each chat, call read_chat, then propose_reply with the reply Daniel would send.
   Replies are only proposals: Daniel approves each one before it is sent. Never claim to be anything
   other than Daniel, never invent facts about him, never push for anything she hasn't signalled interest in.
5. Finish with a two-line summary."""

TINDER_SYSTEM = f"""You run Daniel's Tinder account for one daily session. Persona and voice:

{(HERE / "persona.md").read_text()}

Session plan:
1. Call next_profile repeatedly. Hard rules are already enforced by the tool. For each profile it returns,
   decide like or skip from Daniel's preferences, then call like_profile or skip_profile with a short reason.
   Tinder likes carry no comment; the reason is only for Daniel's log.
2. Stop when a tool reports no likes left or no more profiles.
3. Call list_chats. Every match must get either a message or an unmatch. For each one, call read_chat
   (it returns her profile and the messages so far), then either propose_reply with the message Daniel
   would send (for a new match: an opener that hooks on something specific in her profile), or
   propose_unmatch with a short reason if she fails Daniel's hard rules or is clearly not a fit.
   Both are only proposals: Daniel approves each one before anything happens. Never claim to be anything
   other than Daniel, never invent facts about him.
4. Finish with a two-line summary."""


def record(name, action, detail):
    rows.append((f"{datetime.now():%H:%M}", name, action, detail))
    log(f"{state['app']} {name} {action}: {detail}")


@beta_tool
def next_profile() -> str:
    """Show the next Hinge profile that passes Daniel's hard rules (age, kids, intentions).
    Profiles failing the rules are skipped automatically. Returns the profile fields, one per line."""
    if not state["likes_left"]:
        return "No likes left today. Stop liking and move on to the chats."
    while state["seen"] < MAX_PROFILES:
        skip_button = device(**HINGE["skip"])
        if not skip_button.exists(timeout=5):
            return "No more profiles right now. Move on to the chats."
        name = skip_button.info["contentDescription"].removeprefix("Skip ")
        lines = read_profile(device)
        state["seen"] += 1
        reason = rule_verdict(lines)
        if not reason:
            state["current"] = name
            return f"Name: {name}\n" + "\n".join(lines)
        tap(device, HINGE["skip"])
        record(name, "skip", f"rule: {reason}")
        time.sleep(random.uniform(4, 10))
    return "Profile limit for this session reached. Move on to the chats."


@beta_tool
def skip_profile(reason: str) -> str:
    """Skip the profile last returned by next_profile.

    Args:
        reason: Short reason, for Daniel's log.
    """
    tap(device, HINGE["skip"])
    record(state["current"], "skip", reason)
    time.sleep(random.uniform(4, 12))
    return "skipped"


@beta_tool
def like_with_comment(comment: str) -> str:
    """Like the profile last returned by next_profile and attach a comment.

    Args:
        comment: The comment in Daniel's voice, one or two sentences, no emojis.
    """
    send_like(device, HINGE, comment)
    if out_of_likes(device):
        state["likes_left"] = False
        record(state["current"], "like UNCONFIRMED (limit hit)", comment)
        return "Hinge says no likes left today. Stop liking and move on to the chats."
    record(state["current"], "like + comment", comment)
    time.sleep(random.uniform(4, 12))
    return "sent"


def bounds_center(bounds):
    left, top, right, bottom = map(int, bounds.replace("][", ",").strip("[]").split(","))
    return (left + right) // 2, (top + bottom) // 2


def wait_for_node(matches, timeout_s=10):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for node in ET.fromstring(device.dump_hierarchy()).iter("node"):
            if matches(node):
                return node
        time.sleep(1)
    return None


@beta_tool
def next_incoming_like() -> str:
    """Open the next person in Hinge's Likes You tab who passes Daniel's hard rules.
    People failing the rules are skipped automatically. Returns the profile fields, one per line."""
    while state["incoming_seen"] < MAX_INCOMING:
        for _ in range(3):
            if device(**INCOMING["tab"]).exists(timeout=3):
                break
            device.press("back")
            time.sleep(2)
        else:
            device.screenshot(str(HERE / "runs" / f"{datetime.now():%Y-%m-%d-%H%M}-no-likes-tab.png"))
        tap(device, INCOMING["tab"])
        time.sleep(3)
        card = device(**INCOMING["card"])
        if card.exists(timeout=5):
            card.click()
            time.sleep(4)
        match = device(**INCOMING["match"])
        if not match.exists(timeout=3):
            return "No incoming likes left. Move on to the chats."
        name = match.info["contentDescription"].removeprefix("Match with ").strip()
        lines = read_profile(device)
        state["incoming_seen"] += 1
        state["current"] = name
        reason = rule_verdict(lines)
        if not reason:
            return f"Name: {name}\n" + "\n".join(lines)
        tap(device, INCOMING["skip"])
        record(name, "incoming skip", f"rule: {reason}")
        time.sleep(random.uniform(4, 10))
    return "Incoming limit for this session reached. Move on to the chats."


@beta_tool
def match_incoming(comment: str) -> str:
    """Like back the person last returned by next_incoming_like with a comment, creating a match.

    Args:
        comment: The comment in Daniel's voice, one or two sentences, no emojis.
    """
    name = state["current"]
    tap(device, INCOMING["match"])
    field = wait_for_node(lambda node: node.get("class") == "android.widget.EditText")
    if field is None:
        device.screenshot(str(HERE / "runs" / f"{datetime.now():%Y-%m-%d-%H%M%S}-no-match-sheet.png"))
        raise RuntimeError("match sheet did not open")
    device.click(*bounds_center(field.get("bounds")))
    time.sleep(1)
    type_slowly(device, comment)
    time.sleep(random.uniform(1.5, 3))
    confirm = wait_for_node(lambda node: node.get("text") == f"Match with {name}")
    if confirm is None:
        device.press("back")
        confirm = wait_for_node(lambda node: node.get("text") == f"Match with {name}")
    if confirm is None:
        raise RuntimeError("match confirm button not found")
    device.click(*bounds_center(confirm.get("bounds")))
    time.sleep(5)
    if wait_for_node(lambda node: node.get("text") == "Cancel", timeout_s=3) is not None:
        raise RuntimeError(f"match with {name} not confirmed; still on the match screen")
    record(state["current"], "incoming match + comment", comment)
    time.sleep(random.uniform(4, 10))
    return "matched"


@beta_tool
def skip_incoming(reason: str) -> str:
    """Remove the person last returned by next_incoming_like from Likes You.

    Args:
        reason: Short reason, for Daniel's log.
    """
    tap(device, INCOMING["skip"])
    record(state["current"], "incoming skip", reason)
    time.sleep(random.uniform(4, 10))
    return "skipped"


@beta_tool
def next_tinder_profile() -> str:
    """Show the next Tinder profile that passes Daniel's hard rules (age, kids, intentions).
    Profiles failing the rules are skipped automatically. Returns the profile fields, one per line."""
    if not state["likes_left"]:
        return "No likes left today. Stop and summarize."
    while state["seen"] < MAX_PROFILES:
        card = tinder.next_card(device)
        if card is None:
            return "No more profiles right now. Stop and summarize."
        if card["ad"]:
            tinder.screenshot(device, "ad")
            tinder.skip(device)
            record(card["label"], "skip", "ad, not a profile")
            time.sleep(random.uniform(2, 5))
            continue
        name, lines = tinder.read_profile(device)
        state["seen"] += 1
        reason = rule_verdict(lines)
        if not reason:
            state["current"] = name
            return f"Name: {name}\n" + "\n".join(lines)
        tinder.skip(device)
        record(name, "skip", f"rule: {reason}")
        time.sleep(random.uniform(4, 10))
    return "Profile limit for this session reached. Stop and summarize."


@beta_tool
def skip_tinder_profile(reason: str) -> str:
    """Pass on the profile last returned by next_profile.

    Args:
        reason: Short reason, for Daniel's log.
    """
    tinder.skip(device)
    record(state["current"], "skip", reason)
    time.sleep(random.uniform(4, 12))
    return "skipped"


@beta_tool
def like_tinder_profile(reason: str) -> str:
    """Like the profile last returned by next_profile.

    Args:
        reason: Short reason for the like, for Daniel's log.
    """
    result = tinder.like(device)
    if result == "out of likes":
        state["likes_left"] = False
        record(state["current"], "like UNCONFIRMED (limit hit)", reason)
        return "Tinder says no likes left. Stop and summarize."
    record(state["current"], "like + MATCH" if result == "match" else "like", reason)
    time.sleep(random.uniform(4, 12))
    return "matched" if result == "match" else "liked"


next_tinder_profile.name = "next_profile"
skip_tinder_profile.name = "skip_profile"
like_tinder_profile.name = "like_profile"


@beta_tool
def list_chats() -> str:
    """List matches where it is Daniel's turn: new matches without messages and chats waiting for his reply."""
    if state["app"] == "tinder":
        chats = tinder_chat.list_chats(device)
        return "\n".join(f"{name} ({status})" for name, status in chats) if chats else "No chats waiting for Daniel."
    names = list_your_turn_chats(device)
    return "\n".join(names) if names else "No chats waiting for a reply."


@beta_tool
def read_chat(name: str) -> str:
    """Open the chat with a match and return the visible messages, each prefixed with 'her:' or 'me:'.

    Args:
        name: The match's name exactly as returned by list_chats.
    """
    if state["app"] == "tinder":
        tinder_chat.open_chat(device, name)
        profile = tinder_chat.read_match_profile(device)
        messages = tinder_chat.read_open_chat(device) or ["(no messages yet)"]
        return "Her profile:\n" + "\n".join(profile) + "\n\nMessages:\n" + "\n".join(messages)
    open_chat(device, name)
    return "\n".join(read_open_chat(device))


@beta_tool
def propose_reply(name: str, reply: str) -> str:
    """Queue a reply for Daniel's approval. Nothing is sent until he approves it.

    Args:
        name: The match's name exactly as returned by list_chats.
        reply: The reply in Daniel's voice.
    """
    number = len(proposals) + len(unmatches) + 1
    proposals[number] = (name, reply)
    return f"queued as #{number}"


@beta_tool
def propose_unmatch(name: str, reason: str) -> str:
    """Queue an unmatch for Daniel's approval. Nothing happens until he approves it.

    Args:
        name: The match's name exactly as returned by list_chats.
        reason: Why she is not a fit, for Daniel's approval email.
    """
    number = len(proposals) + len(unmatches) + 1
    unmatches[number] = (name, reason)
    return f"queued as #{number}"


def run_agent(no_likes=False):
    client = create_client()
    system = SYSTEM
    tools = [list_chats, read_chat, propose_reply]
    if state["app"] == "tinder":
        system = TINDER_SYSTEM
        tools = [next_tinder_profile, skip_tinder_profile, like_tinder_profile, list_chats, read_chat, propose_reply, propose_unmatch]
    elif not no_likes:
        tools = [next_profile, skip_profile, like_with_comment, next_incoming_like, match_incoming, skip_incoming, *tools]
    instruction = f"Start today's session ({datetime.now():%A %Y-%m-%d})."
    if no_likes:
        instruction += " Likes are exhausted today. Only check chats and propose replies."
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        thread=False,
        max_tokens=16000,
        output_config={"effort": "medium"},
        system=system,
        tools=tools,
        messages=[{"role": "user", "content": instruction}],
    )
    final = runner.until_done()
    if final.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {final.stop_details}")
    return "\n".join(block.text for block in final.content if block.type == "text")


def approve_and_send():
    if not proposals and not unmatches:
        return
    app = state["app"].capitalize()
    for number, (name, reply) in proposals.items():
        approvals.send(f"[{number}] {app}: {name}\n→ {reply}\n\ny{number} send · n{number} skip · e{number} <text> edit")
    for number, (name, reason) in unmatches.items():
        approvals.send(f"[{number}] {app}: UNMATCH {name}\nWhy: {reason}\n\ny{number} unmatch · n{number} keep")
    decisions = approvals.wait_for_decisions(set(proposals) | set(unmatches), APPROVAL_WINDOW_S)
    chat = tinder_chat if state["app"] == "tinder" else None
    for number, (name, reply) in proposals.items():
        verb, text = decisions.get(number, ("expired", ""))
        if verb in ("y", "e"):
            message = text if verb == "e" and text else reply
            (chat.open_chat if chat else open_chat)(device, name)
            (chat.send_in_open_chat if chat else send_in_open_chat)(device, message)
            record(name, "reply sent", message)
        else:
            record(name, "reply not sent", f"{verb}: {reply}")
    for number, (name, reason) in unmatches.items():
        verb, _ = decisions.get(number, ("expired", ""))
        if verb == "y":
            tinder_chat.open_chat(device, name)
            tinder_chat.unmatch_open_chat(device, name)
            record(name, "unmatched", reason)
        else:
            record(name, "kept", f"{verb}: unmatch proposed ({reason})")
    approvals.send(f"cupid-daemon {app}: {sum(1 for r in rows if r[2] == 'reply sent')} replies sent, {sum(1 for r in rows if r[2] == 'unmatched')} unmatched.")


def main():
    global device, MAX_PROFILES
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-likes", action="store_true")
    parser.add_argument("--device", default=os.environ.get("PHONE_ADB"))
    parser.add_argument("--app", choices=["hinge", "tinder"], default="hinge")
    parser.add_argument("--max-profiles", type=int, default=MAX_PROFILES)
    args = parser.parse_args()
    MAX_PROFILES = args.max_profiles
    state["app"] = args.app
    device = u2.connect(args.device)
    device.app_start(tinder.PACKAGE if args.app == "tinder" else HINGE["package"])
    time.sleep(5)
    try:
        summary = run_agent(no_likes=args.no_likes)
        log(f"agent summary: {summary}")
        approve_and_send()
    finally:
        write_report(f"{args.app}-agent", rows)


if __name__ == "__main__":
    main()
