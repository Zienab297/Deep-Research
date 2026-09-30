"""OpenRouter spend tracking (Task 7).

Cognify does not return its cost, so we read the key's total usage before and
after each document and take the difference. Use a dedicated key, otherwise
other requests on the same key get counted. Usage numbers can lag a few
seconds, so we poll until two readings match.
"""
import os
import time

import httpx

_URL = "https://openrouter.ai/api/v1/key"


def _key() -> str | None:
    # Assumption: the key is in one of these variables in .env. Adjust if not.
    return os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY")


def usage() -> float:
    """Total spend on the key so far, in USD."""
    r = httpx.get(_URL, headers={"Authorization": f"Bearer {_key()}"}, timeout=15)
    r.raise_for_status()
    return float(r.json()["data"]["usage"])


def settled_usage(max_wait: int = 30, interval: int = 3) -> float:
    """Poll until two consecutive readings match, or max_wait seconds pass."""
    prev = usage()
    waited = 0
    while waited < max_wait:
        time.sleep(interval)
        waited += interval
        cur = usage()
        if cur == prev:
            return cur
        prev = cur
    return prev