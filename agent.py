import os
import random
import time
from datetime import datetime
from pathlib import Path

import anthropic
import uiautomator2 as u2
from anthropic import beta_tool

import imessage
from hinge_chat import list_your_turn_chats, open_chat, read_open_chat, send_in_open_chat
from swipe import APPS, log, out_of_likes, read_profile, rule_verdict, send_like, tap, write_report

MODEL = "claude-opus-5-5"
MAX_PROFILES = 40
APPROVAL_WINDOW_S = 3 * 60 * 60
HERE = Path(__file__).parent
HINGE = APPS["hinge"]

device = u2.connect(os.environ.get("PHONE_ADB"))
rows = []
proposals = {}
state = {"current": None, "seen": 0, "likes_left": True}

SYSTEM = f"""You run Daniel's Hinge account for one daily session. Persona and voice:

{(HERE / "persona.md").read_text()}

Session plan:
1. Call next_profile repeatedly. Hard rules are already enforced by the tool. For each profile it returns,
   decide like or skip from Daniel's preferences, then call like_with_comment or skip_profile.
   A like always carries a comment that hooks on something specific in her profile, in Daniel's voice,
   one or two sentences, only facts from the persona.
2. Stop liking when a tool reports no likes left or no more profiles.
3. Call list_chats. For each chat, call read_chat, then propose_reply with the reply Daniel would send.
   Replies are only proposals: Daniel approves each one before it is sent. Never claim to be anything
   other than Daniel, never invent facts about him, never push for anything she hasn't signalled interest in.
4. Finish with a two-line summary."""


def record(name, action, detail):
    rows.append((f"{datetime.now():%H:%M}", name, action, detail))
    log(f"hinge {name} {action}: {detail}")


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


@beta_tool
def list_chats() -> str:
    """List matches where it is Daniel's turn to reply."""
    names = list_your_turn_chats(device)
    return "\n".join(names) if names else "No chats waiting for a reply."


@beta_tool
def read_chat(name: str) -> str:
    """Open the chat with a match and return the visible messages, each prefixed with 'her:' or 'me:'.

    Args:
        name: The match's name exactly as returned by list_chats.
    """
    open_chat(device, name)
    return "\n".join(read_open_chat(device))


@beta_tool
def propose_reply(name: str, reply: str) -> str:
    """Queue a reply for Daniel's approval. Nothing is sent until he approves it.

    Args:
        name: The match's name exactly as returned by list_chats.
        reply: The reply in Daniel's voice.
    """
    number = len(proposals) + 1
    proposals[number] = (name, reply)
    return f"queued as #{number}"


def run_agent():
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        tools=[next_profile, skip_profile, like_with_comment, list_chats, read_chat, propose_reply],
        messages=[{"role": "user", "content": f"Start today's session ({datetime.now():%A %Y-%m-%d})."}],
    )
    final = runner.until_done()
    if final.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {final.stop_details}")
    return "\n".join(block.text for block in final.content if block.type == "text")


def approve_and_send():
    if not proposals:
        return
    for number, (name, reply) in proposals.items():
        imessage.send(f"[{number}] {name}\n→ {reply}\n\ny{number} send · n{number} skip · e{number} <text> edit")
    decisions = imessage.wait_for_decisions(set(proposals), APPROVAL_WINDOW_S)
    for number, (name, reply) in proposals.items():
        verb, text = decisions.get(number, ("expired", ""))
        if verb in ("y", "e"):
            message = text if verb == "e" and text else reply
            open_chat(device, name)
            send_in_open_chat(device, message)
            record(name, "reply sent", message)
        else:
            record(name, "reply not sent", f"{verb}: {reply}")
    imessage.send(f"cupid-daemon: {sum(1 for r in rows if r[2] == 'reply sent')} replies sent.")


def main():
    device.app_start(HINGE["package"])
    time.sleep(5)
    try:
        summary = run_agent()
        log(f"agent summary: {summary}")
        approve_and_send()
    finally:
        write_report("hinge-agent", rows)


if __name__ == "__main__":
    main()
