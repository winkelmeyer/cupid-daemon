from pathlib import Path

from llm import create_client

MODEL = "claude-sonnet-5-5"
PERSONA = Path(__file__).parent / "persona.md"


def write_comment(profile_lines):
    client = create_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=PERSONA.read_text(),
        messages=[{
            "role": "user",
            "content": (
                "This is a Hinge profile, one field per line:\n\n"
                + "\n".join(profile_lines)
                + "\n\nWrite the comment to send with a like, following the persona and its rules. "
                "Only use facts from the persona. Return the comment text only, no quotes."
            ),
        }],
    )
    comment = response.content[0].text.strip().strip('"')
    if not comment or len(comment) > 220:
        raise RuntimeError(f"unusable comment from model: {comment!r}")
    return comment
