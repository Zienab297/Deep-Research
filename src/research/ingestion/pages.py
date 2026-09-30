"""PDF -> list of pages (markdown), one item per page.

pymupdf4llm 1.28.2 (with pymupdf-layout) extracts text and tables and runs
Tesseract only on pages it decides need it, so no separate OCR step here.

The OCR mode is set explicitly so the choice is ours, not a library default.
SELECT_KEEP_OLD is the value that was already the default, so behavior is
unchanged. Whether OCR adds useful or noisy text on born-digital pages is
still open: judge it from golden-set failures, and record any change in
PROCESS_LOG.md.
"""
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm
from pymupdf4llm.helpers.document_layout import OCRMode

from research import config

OCR_MODE = OCRMode.SELECT_KEEP_OLD


@dataclass
class Page:
    file: str
    number: int  # 1-based
    text: str

    def as_document(self) -> str:
        """Text sent to Cognee. The header is how answers get cited."""
        return f"[source: {self.file} | page {self.number}]\n{self.text}"


def extract_pages(pdf_path) -> list[Page]:
    path = Path(pdf_path)
    chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True, use_ocr=OCR_MODE)
    pages = []
    for i, chunk in enumerate(chunks, start=1):
        text = (chunk.get("text") or "").strip()
        if len(text) >= config.MIN_PAGE_CHARS:
            pages.append(Page(file=path.name, number=i, text=text))
    return pages