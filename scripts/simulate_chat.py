import sys
from datetime import datetime
from pathlib import Path

from anthropic import beta_tool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent
import mail as approvals
from llm import create_client

MATCH = "Sam"
TURNS = 3
APPROVAL_WINDOW_S = 30 * 60
POLL_S = 15
PROFILE = """28, she/her. Looking for: something casual, open to more.
Prompt — My simple pleasures: Coffee on a slow Sunday and long walks.
Prompt — Together, we could: Go climbing or find live music.
Prompt — I'm looking for: someone who can keep up on a hike.
She liked one of Daniel's photos; they just matched."""

history = []


@beta_tool
def list_chats() -> str:
    """List matches where it is Daniel's turn to reply."""
    return MATCH


@beta_tool
def read_chat(name: str) -> str:
    """Open the chat with a match and return the visible messages, each prefixed with 'her:' or 'me:'.

    Args:
        name: The match's name exactly as returned by list_chats.
    """
    if name != MATCH:
        raise RuntimeError(f"chat with {name} not found in Matches")
    return "\n".join(f"{side}: {text}" for side, text in history)


def her_message(client):
    transcript = "\n".join(f"{'You' if side == 'her' else 'Daniel'}: {text}" for side, text in history)
    response = client.messages.create(
        model=agent.MODEL,
        max_tokens=1000,
        system=f"You are role-playing a Hinge match named {MATCH} to test a chat assistant. Her profile:\n{PROFILE}\n"
        "Write only her next message: casual, one or two short sentences, the way people text on Hinge.",
        messages=[{"role": "user", "content": transcript or "Write her opening message to Daniel."}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def propose(client):
    agent.proposals.clear()
    runner = client.beta.messages.tool_runner(
        model=agent.MODEL,
        thread=False,
        max_tokens=16000,
        output_config={"effort": "medium"},
        system=agent.SYSTEM,
        tools=[list_chats, read_chat, agent.propose_reply],
        messages=[{"role": "user", "content": "Likes are exhausted today. Only check chats and propose replies."}],
    )
    runner.until_done()
    if len(agent.proposals) != 1:
        raise RuntimeError(f"expected one proposal, got {len(agent.proposals)}")
    return agent.proposals[1][1]


def approve(turn, reply):
    approvals.send(
        f"[1] {MATCH} (SIMULATION turn {turn}/{TURNS})\n"
        + "\n".join(f"{side}: {text}" for side, text in history)
        + f"\n\n→ {reply}\n\ny1 send · n1 skip · e1 <text> edit"
    )
    print(f"approval email sent for turn {turn}; reply y1 / n1 / e1 <text>", flush=True)
    return approvals.wait_for_decisions({1}, APPROVAL_WINDOW_S, poll_s=POLL_S).get(1, ("expired", ""))


def main():
    client = create_client()
    history.append(("her", her_message(client)))
    print(f"her: {history[-1][1]}", flush=True)
    for turn in range(1, TURNS + 1):
        reply = propose(client)
        print(f"proposed: {reply}", flush=True)
        verb, text = approve(turn, reply)
        print(f"decision: {verb} {text}".strip(), flush=True)
        if verb not in ("y", "e"):
            break
        history.append(("me", text if verb == "e" and text else reply))
        history.append(("her", her_message(client)))
        print(f"her: {history[-1][1]}", flush=True)
    out = agent.HERE / "runs" / f"{datetime.now():%Y-%m-%d-%H%M}-simulated-chat.md"
    out.write_text("# Simulated chat (nothing sent on Hinge)\n\n" + "\n\n".join(f"**{side}:** {text}" for side, text in history) + "\n")
    approvals.send(f"cupid-daemon simulation done: {len(history)} messages, transcript in {out.name}")
    print(f"transcript: {out}", flush=True)


if __name__ == "__main__":
    main()
