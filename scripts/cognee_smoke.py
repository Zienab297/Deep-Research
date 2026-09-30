"""Smoke test: Cognee via OpenRouter (LLM) + fastembed (embeddings).

Run from the repo root:  python scripts/cognee_smoke.py
WARNING: prunes all Cognee data. Fine now, never run it against real data later.
Prints the raw search result shape so we can format context correctly.
"""
import asyncio

from dotenv import load_dotenv

load_dotenv()  # must run before cognee is imported

import cognee  # noqa: E402
cognee.config.system_root_directory("D:/cg/system")
cognee.config.data_root_directory("D:/cg/data")

try:
    from cognee import SearchType  # noqa: E402
except ImportError:
    from cognee.api.v1.search import SearchType  # noqa: E402


async def main() -> None:
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    await cognee.add(
        "[source: test.pdf | page 1]\n"
        "The Harbor warehouse lease renews on 1 November 2026 for 18,250 USD."
    )
    await cognee.cognify()

    res = await cognee.search(
        query_text="When does the lease renew?",
        query_type=SearchType.CHUNKS,
    )
    print("result type:", type(res), "len:", len(res))
    for r in res:
        print("item type:", type(r))
        print(repr(r)[:800])


if __name__ == "__main__":
    asyncio.run(main())