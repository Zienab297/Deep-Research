"""PDF -> pages (markdown) plus figures (saved PNGs with captions).

pymupdf4llm 1.28.2 (with pymupdf-layout) extracts text and tables, runs
Tesseract only on pages that need it, and with write_images=True saves every
detected picture (raster or vector) as a PNG.

Checked on a synthetic PDF with the same library version: a "picture" entry in
page_boxes has a text slice (pos) holding the image reference plus any text
found inside the picture, and the caption is the next "caption" box. NOT yet
checked on real arXiv papers (two columns, sub-figures): inspect the output
before trusting it, and record what you find in PROCESS_LOG.md.

The OCR mode is set explicitly so the choice is ours, not a library default.
"""
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm
from PIL import Image
from pymupdf4llm.helpers.document_layout import OCRMode

from research import config

OCR_MODE = OCRMode.SELECT_KEEP_OLD
# Text found inside pictures (axis labels, OCR of diagrams) is kept on the
# Figure for figure search. Keep it out of the page text unless asked.
KEEP_PICTURE_TEXT = getattr(config, "KEEP_PICTURE_TEXT", False)
FIG_DIR = config.DATA_DIR / "figures"
MIN_FIGURE_SIDE = 100  # px; drops logos and icons

_IMG_REF = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_PICTURE_TEXT = re.compile(
    r"<!-- Start of picture text -->(.*?)<!-- End of picture text -->", re.S
)
_BR = re.compile(r"<br\s*/?>")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FIG_LABEL = re.compile(r"^\s*(fig\.?|figure)\s*\d+", re.I)
MAX_CAPTION_CHARS = 300


@dataclass
class Page:
    file: str
    number: int  # 1-based
    text: str

    def as_document(self) -> str:
        """Text sent to Cognee. The header is how answers get cited."""
        return f"[source: {self.file} | page {self.number}]\n{self.text}"


@dataclass
class Figure:
    id: str       # image file stem, unique per document, page and box
    file: str     # source PDF name
    page: int     # 1-based
    image: str    # PNG path relative to config.DATA_DIR (posix)
    caption: str  # "Figure N: ..." text, may be empty
    text: str     # text found inside the picture (labels, OCR), may be empty
    width: int
    height: int


def _rel_to_data(p: Path) -> str:
    try:
        return p.resolve().relative_to(config.DATA_DIR.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def _box_text(text: str, box: dict) -> str:
    a, b = box["pos"]
    return " ".join(text[a:b].split())


def _fallback_caption(text: str, boxes: list, k: int, claimed: set) -> str:
    """Caption missed by the 'next caption box' rule (e.g. placed above the
    picture, or typed as plain text): nearest unclaimed box before or after the
    picture whose text starts with 'Fig. N' / 'Figure N'."""
    best, best_d = None, None
    for j, box in enumerate(boxes):
        if j == k or j in claimed or "pos" not in box:
            continue
        if box.get("class") == "picture":
            continue
        if _FIG_LABEL.match(_box_text(text, box)):
            d = abs(j - k)
            if best_d is None or d < best_d:
                best, best_d = j, d
    if best is None:
        return ""
    return _box_text(text, boxes[best])[:MAX_CAPTION_CHARS]


def _figures_on_page(file: str, number: int, chunk: dict) -> list[Figure]:
    text = chunk.get("text") or ""
    boxes = chunk.get("page_boxes") or []
    # Primary rule: the first caption box after the picture. Sub-figures share
    # the caption below them.
    primary = {}
    for k, box in enumerate(boxes):
        if box.get("class") == "picture":
            primary[k] = next(
                (j for j in range(k + 1, len(boxes))
                 if boxes[j].get("class") == "caption"), None)
    claimed = {j for j in primary.values() if j is not None}
    figs = []
    for k, j in primary.items():
        seg = text[boxes[k]["pos"][0]:boxes[k]["pos"][1]]
        m = _IMG_REF.search(seg)
        if not m:
            continue  # picture box with no written image
        img = Path(m.group(1))
        if not img.exists():
            continue
        with Image.open(img) as im:
            w, h = im.size
        if min(w, h) < MIN_FIGURE_SIDE:
            continue
        if j is not None:
            caption = _box_text(text, boxes[j])
        else:
            caption = _fallback_caption(text, boxes, k, claimed)
        inner = " ".join(
            " ".join(_BR.sub(" ", t).split()) for t in _PICTURE_TEXT.findall(seg)
        )
        figs.append(Figure(
            id=img.stem, file=file, page=number, image=_rel_to_data(img),
            caption=caption, text=inner, width=w, height=h,
        ))
    return figs


def extract(pdf_path) -> tuple[list[Page], list[Figure]]:
    path = Path(pdf_path)
    out_dir = FIG_DIR / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = pymupdf4llm.to_markdown(
        str(path),
        page_chunks=True,
        use_ocr=OCR_MODE,
        write_images=True,
        image_path=str(out_dir.resolve()),
        image_format="png",
        image_dpi=150,
    )
    pages, figures = [], []
    for i, chunk in enumerate(chunks, start=1):
        figures.extend(_figures_on_page(path.name, i, chunk))
        # Image paths and picture text are not page content: keep them out of
        # what Cognee sees (figure text is searchable via the figure catalog).
        text = _IMG_REF.sub("", chunk.get("text") or "")
        if not KEEP_PICTURE_TEXT:
            text = _PICTURE_TEXT.sub("", text)
        text = _COMMENT.sub("", text).strip()
        if len(text) >= config.MIN_PAGE_CHARS:
            pages.append(Page(file=path.name, number=i, text=text))
    return pages, figures


def extract_pages(pdf_path) -> list[Page]:
    return extract(pdf_path)[0]