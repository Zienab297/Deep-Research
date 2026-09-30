"""Thin wrapper around Cognee (tested version: 1.4.0.dev4)."""
import asyncio
import time
from pathlib import Path

from research import config  # must come before cognee (loads .env)
from research.ingestion.pages import extract_pages
from research.knowledge import cost

import cognee


def configure_cognee() -> None:
    cognee.config.system_root_directory((config.COGNEE_ROOT / "system").as_posix())
    cognee.config.data_root_directory((config.COGNEE_ROOT / "data").as_posix())


configure_cognee()


async def reset() -> None:
    """Wipe all Cognee data. Use before a clean eval run."""
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)


async def _spend() -> float | None:
    """Settled OpenRouter spend, or None if it cannot be read (never blocks ingestion)."""
    try:
        return await asyncio.to_thread(cost.settled_usage)
    except Exception as e:
        print(f"[cost] could not read usage: {e!r}")
        return None


async def ingest_document(pdf_path, dataset: str = config.DEFAULT_WORKSPACE) -> dict:
    """Extract pages, add one Cognee item per page, cognify.

    Returns timing and cost stats. cost_usd is None if usage could not be read.
    """
    pdf_path = Path(pdf_path)

    t0 = time.perf_counter()
    pages = await asyncio.to_thread(extract_pages, pdf_path)
    t1 = time.perf_counter()

    if not pages:
        return {"file": pdf_path.name, "dataset": dataset, "pages": 0,
                "skipped": "no page reached MIN_PAGE_CHARS"}

    before = await _spend()
    t2 = time.perf_counter()
    await cognee.add([p.as_document() for p in pages], dataset_name=dataset)
    await cognee.cognify(datasets=[dataset])
    t3 = time.perf_counter()
    after = await _spend()

    return {
        "file": pdf_path.name,
        "dataset": dataset,
        "pages": len(pages),
        "chars": sum(len(p.text) for p in pages),
        "extract_s": round(t1 - t0, 1),
        "cognee_s": round(t3 - t2, 1),
        "cost_usd": None if before is None or after is None else round(after - before, 4),
    }