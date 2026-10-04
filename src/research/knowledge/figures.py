"""Figure catalog and search.

Local only: figures are matched on caption plus in-picture text with the same
fastembed MiniLM model Cognee uses, so this costs no LLM provider tokens and
does not go through cognify.

Sub-figures that share one caption on the same page are grouped into a single
result, so one figure is returned once with all of its images:
    for rel in result["images"]:
        path = config.DATA_DIR / rel
"""
import json
import shutil
from dataclasses import asdict

import numpy as np

from research import config

CATALOG = config.DATA_DIR / "figures" / "catalog.json"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_model = None
_cache = {"mtime": None, "groups": [], "vecs": None}


def _load() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {}


def save(file: str, figs: list) -> None:
    """Replace this document's figures in the catalog (idempotent per file)."""
    cat = {k: v for k, v in _load().items() if v["file"] != file}
    for f in figs:
        cat[f.id] = asdict(f)
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(cat, indent=2), encoding="utf-8")


def clear() -> None:
    """Delete all saved figures and the catalog."""
    shutil.rmtree(CATALOG.parent, ignore_errors=True)
    _cache.update(mtime=None, groups=[], vecs=None)


def _groups(cat: dict) -> list[dict]:
    """One entry per figure: items with the same file, page and caption merge.
    A figure with no caption stays on its own."""
    groups: dict = {}
    for it in cat.values():
        key = (it["file"], it["page"], it["caption"]) if it["caption"] else it["id"]
        g = groups.get(key)
        if g is None:
            groups[key] = dict(it, images=[it["image"]])
        else:
            g["images"].append(it["image"])
            g["text"] = f"{g['text']} {it['text']}".strip()
    return list(groups.values())


def _embed(texts: list[str]) -> np.ndarray:
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=EMBED_MODEL)
    v = np.array(list(_model.embed(texts)), dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


def search(query: str, k: int = 3, min_score: float = 0.3) -> list[dict]:
    """Top figures for a question. min_score is a first guess: tune it on the
    golden set using the returned scores."""
    cat = _load()
    if not cat:
        return []
    mtime = CATALOG.stat().st_mtime
    if _cache["mtime"] != mtime:
        groups = _groups(cat)
        texts = [f"{g['caption']} {g['text']}".strip() or "figure" for g in groups]
        _cache.update(mtime=mtime, groups=groups, vecs=_embed(texts))
    q = _embed([query])[0]
    scores = _cache["vecs"] @ q
    order = np.argsort(-scores)[:k]
    return [
        dict(_cache["groups"][i], score=float(scores[i]))
        for i in order
        if scores[i] >= min_score
    ]