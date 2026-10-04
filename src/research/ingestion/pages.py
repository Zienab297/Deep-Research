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
FIG_DIR = config.DATA_DIR / "figures"
MIN_FIGURE_SIDE = 100  # px; drops logos and icons

_IMG_REF = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_PICTURE_TEXT = re.compile(
    r"<!-- Start of picture text -->(.*?)<!-- End of picture text -->", re.S
)
_BR = re.compile(r"<br\s*/?>")


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


def _figures_on_page(file: str, number: int, chunk: dict) -> list[Figure]:
    text = chunk.get("text") or ""
    boxes = chunk.get("page_boxes") or []
    figs = []
    for k, box in enumerate(boxes):
        if box.get("class") != "picture":
            continue
        start, end = box["pos"]
        seg = text[start:end]
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
        # Caption = first caption box after the picture. Sub-figures share the
        # caption below them. A caption placed above the picture is missed.
        caption = ""
        for nxt in boxes[k + 1:]:
            if nxt.get("class") == "caption":
                a, b = nxt["pos"]
                caption = " ".join(text[a:b].split())
                break
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
        # Image paths are not content, so keep them out of what Cognee sees.
        text = _IMG_REF.sub("", chunk.get("text") or "").strip()
        if len(text) >= config.MIN_PAGE_CHARS:
            pages.append(Page(file=path.name, number=i, text=text))
    return pages, figures


def extract_pages(pdf_path) -> list[Page]:
    return extract(pdf_path)[0]