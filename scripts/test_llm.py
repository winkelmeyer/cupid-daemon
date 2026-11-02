import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anthropic import beta_tool

from llm import create_client

calls = []


@beta_tool
def read_test_status() -> str:
    """Read the synthetic integration-test status."""
    calls.append("read")
    return "GATEWAY_TOOL_OK"


with patch("uiautomator2.connect"):
    import agent

client = create_client()
runner = client.beta.messages.tool_runner(
    model=agent.MODEL,
    thread=False,
    max_tokens=1000,
    output_config={"effort": "medium"},
    system="Call read_test_status exactly once, then repeat its result verbatim.",
    tools=[read_test_status],
    messages=[{"role": "user", "content": "Test the connection now."}],
)
final = runner.until_done()
result = "\n".join(b.text for b in final.content if b.type == "text").strip()
assert calls == ["read"], f"Expected one tool invocation, got {len(calls)}"
assert result == "GATEWAY_TOOL_OK", f"Unexpected test result: {result!r}"
print(f"PASS {agent.MODEL}: tool_use → local tool → tool_result → {result}")
