"""Ingest PDFs into Cognee. Resumable: files already ingested are skipped.

Run from the repo root.

  # first run, wipes all Cognee data and the saved progress:
  python scripts/ingest_all.py --reset --limit 1 data/pdfs/<one>.pdf

  # later: continue where you stopped (no paths = everything in data/pdfs)
  python scripts/ingest_all.py --limit 2

  # re-ingest a file that is already marked ok:
  python scripts/ingest_all.py --force data/pdfs/<one>.pdf

--limit N ingests at most N files this run, so you can spend a daily token
budget in pieces. Progress is saved to data/ingest_state.json after each file.
"""
import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from research import config  # keep before anything that imports cognee
from research.knowledge import store

STATE = config.DATA_DIR / "ingest_state.json"


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2))


async def main(files: list[Path], reset: bool, force: bool, limit: int | None) -> None:
    if reset:
        print("Resetting Cognee data and saved progress...")
        await store.reset()
        state = {}
        save_state(state)
    else:
        state = load_state()

    attempted = 0
    stopped_by_limit = False
    for f in files:
        if not force and state.get(f.name, {}).get("status") == "ok":
            print(f"skip (already ingested): {f.name}")
            continue
        if limit is not None and attempted >= limit:
            print(f"--limit {limit} reached, stopping.")
            break
        attempted += 1

        print(f"\n>>> {f.name}")
        try:
            stats = await store.ingest_document(f)
        except store.DailyLimitReached as e:
            print("\nProvider daily limit reached. Progress is saved, rerun later to resume.")
            print(e)
            stopped_by_limit = True
            break
        except Exception as e:  # keep going, record the failure
            stats = {"file": f.name, "status": "error", "error": repr(e)}
        print(stats)
        state[f.name] = stats
        save_state(state)

    counts = Counter(s.get("status", "?") for s in state.values())
    print("\n=== Summary (all files in saved progress) ===")
    print(dict(counts))
    print("pages:", sum(s.get("pages", 0) for s in state.values()))
    print("cognee seconds:", round(sum(s.get("cognee_s", 0) for s in state.values()), 1))
    if stopped_by_limit:
        print("Stopped early by the daily limit.")
    print("progress file:", STATE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--reset", action="store_true", help="wipe all Cognee data first")
    ap.add_argument("--force", action="store_true", help="re-ingest files marked ok")
    ap.add_argument("--limit", type=int, default=None, help="max files to ingest this run")
    args = ap.parse_args()
    files = args.paths or sorted(config.PDF_DIR.glob("*.pdf"))
    asyncio.run(main(files, args.reset, args.force, args.limit))