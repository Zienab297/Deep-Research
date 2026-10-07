"""Thin wrapper around Cognee (tested version: 1.4.0.dev4)."""
import asyncio
import time
from pathlib import Path

from research import config  # must come before cognee (loads .env)
from research.ingestion.chunks import chunk_pages
from research.ingestion.pages import extract
from research.knowledge import figures

import cognee

# Items cognified at once. 1 keeps request bursts small, which matters under a
# per-minute token limit. Raise it when your provider limits allow.
COGNIFY_DATA_PER_BATCH = 1

# Best-effort markers for "daily budget used up" in provider error text.
# Unverified against Cognee's wrapped errors: check the first real one you see.
_DAILY_LIMIT_MARKERS = ("per day", "(tpd)", "(rpd)")


class DailyLimitReached(RuntimeError):
    """The provider's daily budget is used up, so retrying today is pointless."""


def configure_cognee() -> None:
    cognee.config.system_root_directory((config.COGNEE_ROOT / "system").as_posix())
    cognee.config.data_root_directory((config.COGNEE_ROOT / "data").as_posix())


configure_cognee()


async def reset() -> None:
    """Wipe all Cognee data and all saved figures. Use before a clean eval run.

    Also required after changing the chunking: Cognee dedupes by content, so
    items from an older chunking would otherwise stay next to the new ones.
    """
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    figures.clear()


def _daily_limit_hit(obj) -> bool:
    text = str(obj).lower()
    return any(m in text for m in _DAILY_LIMIT_MARKERS)


async def ingest_document(pdf_path, dataset: str = config.DEFAULT_WORKSPACE) -> dict:
    """Extract pages and figures, chunk the text, add one Cognee item per
    chunk, cognify.

    Figures (images, captions, in-picture text) go to the local figure catalog,
    not through Cognee, so they cost no LLM tokens.

    status in the returned dict:
      ok      cognify returned and its result shows no error text
      check   cognify returned but the result mentions an error: read cognify_result
      skipped no chunk could be built (no page reached MIN_PAGE_CHARS)
    Raises DailyLimitReached when the provider's daily budget is exhausted.
    """
    pdf_path = Path(pdf_path)

    t0 = time.perf_counter()
    pages, figs = await asyncio.to_thread(extract, pdf_path)
    figures.save(pdf_path.name, figs)  # idempotent per file, safe to rerun
    chunks = chunk_pages(pages)
    t1 = time.perf_counter()

    if not chunks:
        return {"file": pdf_path.name, "dataset": dataset, "pages": len(pages),
                "chunks": 0, "figures": len(figs), "status": "skipped",
                "skipped": "no chunk could be built (no page reached MIN_PAGE_CHARS)"}

    await cognee.add([c.as_document() for c in chunks], dataset_name=dataset)
    try:
        result = await cognee.cognify(
            datasets=[dataset], data_per_batch=COGNIFY_DATA_PER_BATCH
        )
    except Exception as e:
        if _daily_limit_hit(e):
            raise DailyLimitReached(str(e)[:300]) from e
        raise
    t2 = time.perf_counter()

    result_text = str(result)
    if _daily_limit_hit(result_text):
        raise DailyLimitReached(result_text[:300])

    return {
        "file": pdf_path.name,
        "dataset": dataset,
        "pages": len(pages),
        "chunks": len(chunks),
        "figures": len(figs),
        "chars": sum(len(c.text) for c in chunks),
        "extract_s": round(t1 - t0, 1),
        "cognee_s": round(t2 - t1, 1),
        "status": "check" if "error" in result_text.lower() else "ok",
        "cognify_result": result_text[:300],
    }