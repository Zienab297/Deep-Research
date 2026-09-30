"""Ingest PDFs into Cognee and record time and cost per document.

Run from the repo root.

  # first run, wipes all Cognee data, one file:
  python scripts/ingest_all.py --reset data/pdfs/<one>.pdf

  # later, add more files without wiping:
  python scripts/ingest_all.py data/pdfs/a.pdf data/pdfs/b.pdf

  # no paths given: everything in data/pdfs
  python scripts/ingest_all.py
"""
import argparse
import asyncio
import json
from pathlib import Path

from research import config  # keep before anything that imports cognee
from research.knowledge import store


async def main(files: list[Path], reset: bool) -> None:
    if reset:
        print("Resetting Cognee data...")
        await store.reset()

    rows = []
    for f in files:
        print(f"\n>>> {f.name}")
        try:
            stats = await store.ingest_document(f)
        except Exception as e:  # keep going, record the failure
            stats = {"file": f.name, "error": repr(e)}
        print(stats)
        rows.append(stats)

    out = config.DATA_DIR / "ingest_stats.json"
    out.write_text(json.dumps(rows, indent=2))

    ok = [r for r in rows if "error" not in r and r.get("pages")]
    costs = [r["cost_usd"] for r in ok if r.get("cost_usd") is not None]
    print("\n=== Summary ===")
    print("documents ingested:", len(ok), "of", len(rows))
    print("pages:", sum(r["pages"] for r in ok))
    print("cognee seconds:", round(sum(r["cognee_s"] for r in ok), 1))
    if costs:
        print("cost USD:", round(sum(costs), 4), "| per document:", round(sum(costs) / len(costs), 4))
    print("saved to", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--reset", action="store_true", help="wipe all Cognee data first")
    args = ap.parse_args()
    files = args.paths or sorted(config.PDF_DIR.glob("*.pdf"))
    asyncio.run(main(files, args.reset))