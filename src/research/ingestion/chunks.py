"""Pages (markdown) -> structure-aware chunks with page and section metadata.

Parsing step (markdown -> blocks):
  * repeated running headers/footers and bare page numbers are removed
  * text is split into heading / table / text blocks
  * a paragraph cut by a page break is stitched back together
  * the heading stack gives every block a section path ("3 Method > 3.1 Loss")
  * the References section is dropped (SKIP_REFERENCES)

Chunking step (blocks -> chunks):
  * heading levels come from numbering (I. / A. / 1.1) because the layout
    model emits every heading as "##"; "Table N" / "Fig. N" labels are text
  * a new chunk starts at every level 1-2 heading, at a level-3 heading once
    the chunk holds SUBSECTION_MIN_CHARS, and when MAX_CHARS is hit
  * tables are never cut mid-row; oversize tables split with the header repeated
  * oversize paragraphs split on sentences
  * size splits carry a small text overlap (OVERLAP_CHARS); section splits don't
  * each chunk records page_start/page_end, so citations stay exact

Works on any objects with .file, .number, .text (pages.Page).
"""
import re
from collections import Counter
from dataclasses import dataclass

from research import config

MAX_CHARS = getattr(config, "CHUNK_MAX_CHARS", 2000)
OVERLAP_CHARS = getattr(config, "CHUNK_OVERLAP_CHARS", 200)
SKIP_REFERENCES = getattr(config, "SKIP_REFERENCES", True)
# A level-3 heading (subsection) starts a new chunk only if the current chunk
# already holds this much text, so short subsections don't become tiny chunks.
SUBSECTION_MIN_CHARS = getattr(config, "CHUNK_SUBSECTION_MIN_CHARS", 600)

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_SENT = re.compile(r"(?<=[.!?])\s+")
_REFS = re.compile(r"^(\d+\.?\s+)?(references|bibliography|works cited)$", re.I)
_TAGS = re.compile(r"<[^>]+>")
# Table/figure labels that the layout model sometimes emits as headings.
_CAPTION_HEAD = re.compile(r"^(table|fig\.?|figure)\s*([0-9]+|[IVXL]+)\b", re.I)
# Numbering styles, used because the layout model makes every heading "##".
_ROMAN = re.compile(r"^(X{0,2})(IX|IV|V?I{0,3})\.\s")  # I. ... XX. (not C.)
_DOTTED = re.compile(r"^(\d+(?:\.\d+)+)\.?\s")        # 1.1  1.1.1
_NUM = re.compile(r"^\d+\.?\s")                         # 1  1.
_LETTER = re.compile(r"^[A-Z]\.\s")                      # A.
_SENTENCE_END = (".", "!", "?", ":", ";", ")", '"')


@dataclass
class Chunk:
    file: str
    index: int
    page_start: int
    page_end: int
    section: str
    text: str

    def as_document(self) -> str:
        """Text sent to Cognee. The header is how answers get cited."""
        pages = (f"page {self.page_start}" if self.page_start == self.page_end
                 else f"pages {self.page_start}-{self.page_end}")
        sect = f" | section: {self.section}" if self.section else ""
        return f"[source: {self.file} | {pages}{sect}]\n{self.text}"


@dataclass
class _B:
    kind: str  # heading | table | text
    text: str
    p0: int
    p1: int
    level: int = 0
    title: str = ""
    sect: str = ""
    carried: bool = False


# ---------------------------------------------------------------- parsing
def _clean_title(t: str) -> str:
    return re.sub(r"[*_`]+", "", _TAGS.sub("", t)).strip()


def _infer_level(title: str, md_level: int) -> int:
    """Heading level from numbering when it is recognisable, else the markdown
    level. The document title (level 1) is left alone."""
    if md_level == 1:
        return 1
    m = _ROMAN.match(title)
    if m and (m.group(1) or m.group(2)):
        return 2
    m = _DOTTED.match(title)
    if m:
        return 2 + m.group(1).count(".")
    if _NUM.match(title):
        return 2
    if _LETTER.match(title):
        return 3
    return md_level


def _norm(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def _strip_running(pages) -> dict[int, str]:
    """Remove first/last lines that repeat on many pages (headers, footers,
    page numbers). Only for documents with 4+ pages."""
    texts = {p.number: p.text for p in pages}
    if len(pages) < 4:
        return texts
    cnt: Counter = Counter()
    for t in texts.values():
        ls = [l for l in t.splitlines() if l.strip()]
        if ls:
            cnt.update({_norm(ls[0]), _norm(ls[-1])})
    bad = {k for k, v in cnt.items() if v >= max(3, len(pages) // 2)}
    out = {}
    for n, t in texts.items():
        ls = t.splitlines()
        idx = [i for i, l in enumerate(ls) if l.strip()]
        drop = {i for i in ((idx[0], idx[-1]) if idx else ()) if _norm(ls[i]) in bad}
        out[n] = "\n".join(l for i, l in enumerate(ls) if i not in drop)
    return out


def _pieces(raw: str):
    """Split a raw paragraph so a heading glued to following text is separate."""
    lines = raw.split("\n")
    if len(lines) > 1 and _HEADING.match(lines[0]):
        return [lines[0], "\n".join(lines[1:]).strip()]
    return [raw]


def _blocks(pages) -> list[_B]:
    texts = _strip_running(pages)
    out: list[_B] = []
    for p in pages:
        first = True
        for para in re.split(r"\n\s*\n", texts[p.number]):
            for raw in _pieces(para.strip()):
                if not raw:
                    continue
                m = _HEADING.match(raw) if "\n" not in raw else None
                if m and _CAPTION_HEAD.match(_clean_title(m.group(2))):
                    plain = _TAGS.sub("", re.sub(r"^#+\s*", "", raw))
                    b = _B("text", plain, p.number, p.number)  # label, not a section
                elif m:
                    title = _clean_title(m.group(2))
                    b = _B("heading", raw, p.number, p.number,
                           _infer_level(title, len(m.group(1))), title)
                elif raw.startswith("|"):
                    b = _B("table", raw, p.number, p.number)
                else:
                    b = _B("text", raw, p.number, p.number)
                prev = out[-1] if out else None
                if (first and b.kind == "text" and prev and prev.kind == "text"
                        and prev.p1 == p.number - 1
                        and not prev.text.rstrip().endswith(_SENTENCE_END)
                        and b.text[:1].islower()):
                    prev.text += " " + b.text  # paragraph continued across pages
                    prev.p1 = p.number
                else:
                    out.append(b)
                first = False
    return out


# --------------------------------------------------------------- chunking
def _split(b: _B) -> list[str]:
    """Break one block into pieces of at most MAX_CHARS."""
    if len(b.text) <= MAX_CHARS:
        return [b.text]
    if b.kind == "table":
        rows = b.text.split("\n")
        head, out, cur = rows[:2], [], rows[:2]
        for r in rows[2:]:
            if len("\n".join(cur + [r])) > MAX_CHARS and len(cur) > len(head):
                out.append("\n".join(cur))
                cur = list(head)
            cur.append(r)
        out.append("\n".join(cur))
        return out
    out, cur = [], ""
    for s in _SENT.split(b.text):
        while len(s) > MAX_CHARS:  # no sentence break: hard split
            if cur:
                out.append(cur)
                cur = ""
            out.append(s[:MAX_CHARS])
            s = s[MAX_CHARS:]
        if cur and len(cur) + 1 + len(s) > MAX_CHARS:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_pages(pages) -> list[Chunk]:
    if not pages:
        return []
    file = pages[0].file
    path: list[tuple[int, str]] = []
    chunks: list[Chunk] = []
    cur: list[_B] = []
    skip_level = None
    blocks = _blocks(pages)
    # A single level-1 heading is the document title: it labels the first
    # chunk only and is dropped from the section path from the next heading on.
    lone_title = sum(1 for x in blocks if x.kind == "heading" and x.level == 1) == 1

    def section() -> str:
        return " > ".join(t for _, t in path)

    def flush(carry: bool) -> None:
        nonlocal cur
        content = [c for c in cur if c.kind != "heading" and not c.carried]
        if not content:
            cur = [c for c in cur if not c.carried]  # keep pending headings
            return
        chunks.append(Chunk(
            file=file, index=len(chunks),
            page_start=min(c.p0 for c in cur), page_end=max(c.p1 for c in cur),
            section=content[0].sect,
            text="\n\n".join(c.text for c in cur),
        ))
        keep: list[_B] = []
        if carry:
            n = 0
            for c in reversed(content):
                if c.kind != "text" or n + len(c.text) > OVERLAP_CHARS:
                    break
                keep.insert(0, _B(c.kind, c.text, c.p0, c.p1, sect=c.sect, carried=True))
                n += len(c.text)
        cur = keep

    for b in blocks:
        if skip_level is not None and not (b.kind == "heading" and b.level <= skip_level):
            continue
        if b.kind == "heading":
            if lone_title and b.level >= 2 and path and path[0][0] == 1:
                path.pop(0)
            while path and path[-1][0] >= b.level:
                path.pop()
            path.append((b.level, b.title))
            if SKIP_REFERENCES and _REFS.match(b.title):
                flush(False)
                skip_level = b.level
                continue
            skip_level = None
            new_text = sum(len(c.text) for c in cur
                           if c.kind != "heading" and not c.carried)
            if b.level <= 2 or (b.level == 3 and new_text >= SUBSECTION_MIN_CHARS):
                flush(False)
            b.sect = section()
            cur.append(b)
            continue
        for piece in _split(b):
            size = sum(len(c.text) for c in cur)
            if any(not c.carried and c.kind != "heading" for c in cur) \
                    and size + len(piece) > MAX_CHARS:
                flush(True)
            cur.append(_B(b.kind, piece, b.p0, b.p1, sect=section()))
    flush(False)
    return chunks