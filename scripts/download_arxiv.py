"""Download N arXiv PDFs via the official API (no scraping).

Usage:
  python download_arxiv.py --category cs.CL --query "retrieval augmented generation" --n 10

arXiv API etiquette: one request at a time, at least 3 seconds apart.
"""
import argparse
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}
HEADERS = {"User-Agent": "doc-research-platform/0.1 (contact: you@example.com)"}
DELAY = 3.5


def search(category: str, query: str, n: int) -> list[dict]:
    q = f"cat:{category}"
    if query:
        q += f' AND all:"{query}"'
    params = {
        "search_query": q,
        "start": 0,
        "max_results": n,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    r = requests.get(API, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    papers = []
    for e in root.findall("a:entry", NS):
        abs_url = e.find("a:id", NS).text.strip()
        pdf_url = None
        for link in e.findall("a:link", NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
        papers.append({
            "id": abs_url.rsplit("/abs/", 1)[-1],
            "title": " ".join(e.find("a:title", NS).text.split()),
            "published": e.find("a:published", NS).text,
            "abs_url": abs_url,
            "pdf_url": pdf_url or abs_url.replace("/abs/", "/pdf/"),
        })
    return papers


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="cs.CL")
    ap.add_argument("--query", default="")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default="data/pdfs")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    papers = search(args.category, args.query, args.n)
    print(f"API returned {len(papers)} papers")

    manifest = []
    for p in papers:
        time.sleep(DELAY)
        fname = "arxiv_" + re.sub(r"[^\w.\-]", "_", p["id"]) + ".pdf"
        path = out / fname
        if not path.exists():
            r = requests.get(p["pdf_url"], headers=HEADERS, timeout=120)
            r.raise_for_status()
            path.write_bytes(r.content)
        p["file"] = fname
        p["bytes"] = path.stat().st_size
        manifest.append(p)
        print(f"ok {fname}  {p['title'][:70]}")

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {out / 'manifest.json'}")


if __name__ == "__main__":
    main()