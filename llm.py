import os

import anthropic


def create_client():
    key = os.environ.get(os.environ.get("LLM_KEY_VAR", ""))
    if not key:
        raise RuntimeError("LLM gateway key missing; start with ./run.sh <script.py>")
    return anthropic.Anthropic(
        api_key=key,
        base_url=os.environ["LLM_BASE_URL"],
        timeout=120.0,
        max_retries=0,
    )
