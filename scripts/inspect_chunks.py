"""Review what ingestion would produce for one PDF, without touching Cognee.

    python scripts/inspect_chunks.py paper.pdf
    python scripts/inspect_chunks.py paper.pdf --dump out.md

Prints a per-chunk table plus warnings, and a figure summary. --dump writes
every chunk (as Cognee would see it) to a markdown file for reading.
Record what you find in PROCESS_LOG.md.
"""
import argparse
from collections import Counter
from pathlib import Path

from research.ingestion import chunks as ck
from research.ingestion.pages import extract


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--dump", help="write all chunks to this markdown file")
    args = ap.parse_args()

    pages, figs = extract(args.pdf)
    chunks = ck.chunk_pages(pages)

    print(f"{Path(args.pdf).name}: {len(pages)} pages kept, "
          f"{len(chunks)} chunks, {len(figs)} figures\n")
    print(f"{'#':>3} {'pages':>7} {'chars':>6}  section / start of text")
    for c in chunks:
        pg = str(c.page_start) if c.page_start == c.page_end else f"{c.page_start}-{c.page_end}"
        start = " ".join(c.text.split())[:60]
        print(f"{c.index:>3} {pg:>7} {len(c.text):>6}  {c.section[-40:] or '-'} | {start}")

    # ---- warnings: things to look at by eye
    warns = []
    sizes = [len(c.text) for c in chunks]
    if sizes:
        warns.append(f"chunk size min/median/max: {min(sizes)}/"
                     f"{sorted(sizes)[len(sizes) // 2]}/{max(sizes)} (limit {ck.MAX_CHARS})")
    tiny = [c.index for c in chunks if len(c.text) < 200]
    if tiny:
        warns.append(f"{len(tiny)} chunks under 200 chars: {tiny[:15]}")
    nosec = [c.index for c in chunks if not c.section]
    if nosec:
        warns.append(f"{len(nosec)} chunks with no section (headings not detected?): {nosec[:15]}")
    if chunks and len({c.section for c in chunks}) == 1:
        warns.append("every chunk has the same section: heading detection probably failed")
    seen = Counter(c.text for c in chunks)
    dup = sum(v - 1 for v in seen.values() if v > 1)
    if dup:
        warns.append(f"{dup} duplicate chunks")
    kept = {p.number for p in pages}
    first_last = (min(kept), max(kept)) if kept else None
    if first_last:
        warns.append(f"pages kept: {len(kept)} (first {first_last[0]}, last {first_last[1]})")

    print("\nWarnings / stats")
    for w in warns:
        print(" -", w)

    # ---- figures
    nocap = [f.id for f in figs if not f.caption]
    print(f"\nFigures: {len(figs)}; without caption: {len(nocap)}")
    by_cap = Counter((f.page, f.caption) for f in figs if f.caption)
    shared = sum(1 for v in by_cap.values() if v > 1)
    print(f"Captions shared by several images (sub-figures): {shared}")
    for f in figs[:10]:
        print(f"  p{f.page} {f.width}x{f.height} {f.id}: {f.caption[:70] or '(no caption)'}")

    if args.dump:
        body = "\n\n---\n\n".join(c.as_document() for c in chunks)
        Path(args.dump).write_text(body, encoding="utf-8")
        print(f"\nWrote {len(chunks)} chunks to {args.dump}")


if __name__ == "__main__":
    main()