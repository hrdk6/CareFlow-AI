"""Structure-aware chunking.

1. detect_blocks: turn page text into headings and paragraphs (markdown '#', numbered headings
   such as "3.2 Monitoring", and short ALL-CAPS lines are headings).
2. chunk_structure: pack paragraphs of ONE section into chunks of <= max_words, never crossing a
   section boundary; long paragraphs are split on sentence boundaries; consecutive chunks of the
   same section overlap by up to overlap_words of trailing sentences.
Every chunk remembers its section path ("4. Monitoring > 4.2 Kidney function") and page range.

The alternative "fixed" strategy (sliding word window) exists for the evaluation comparison.
"""
import hashlib
import re
from dataclasses import dataclass

from app.rag.parsing import ParsedDocument

_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+([A-Z][^\n]{1,90})$")
_MD = re.compile(r"^(#{1,4})\s+(.+)$")
_BULLET = re.compile(r"^([-*•]|\d+\))\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")


@dataclass
class Block:
    kind: str  # heading | paragraph
    text: str
    level: int
    page: int


@dataclass
class Chunk:
    index: int
    text: str
    section_path: str
    page_start: int
    page_end: int

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(" ".join(self.text.lower().split()).encode()).hexdigest()


def _heading(line: str) -> tuple[int, str] | None:
    if m := _MD.match(line):
        return len(m.group(1)), m.group(2).strip()
    if (m := _NUMBERED.match(line)) and not line.rstrip().endswith((".", ",", ";")) and len(line.split()) <= 12:
        return m.group(1).count(".") + 1, line.strip()
    letters = [c for c in line if c.isalpha()]
    if (4 <= len(line) <= 80 and letters and all(c.isupper() for c in letters)
            and len(line.split()) <= 10 and not line.endswith(".")):
        return 1, line.strip().title()
    return None


def detect_blocks(parsed: ParsedDocument) -> list[Block]:
    blocks: list[Block] = []

    def flush(paragraph: list[str], page_number: int) -> None:
        if paragraph:
            blocks.append(Block("paragraph", " ".join(paragraph).strip(), 0, page_number))
            paragraph.clear()

    for page in parsed.pages:
        paragraph: list[str] = []
        for raw in page.text.split("\n"):
            line = raw.strip()
            if not line:
                flush(paragraph, page.number)
                continue
            if (h := _heading(line)) is not None:
                flush(paragraph, page.number)
                blocks.append(Block("heading", h[1], h[0], page.number))
                continue
            if _BULLET.match(line):
                flush(paragraph, page.number)
            paragraph.append(line)
        flush(paragraph, page.number)
    return blocks


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def _split_long(text: str, max_words: int) -> list[str]:
    out, cur = [], []
    for sentence in _sentences(text):
        words = sentence.split()
        if len(words) > max_words:  # pathological sentence: hard wrap
            for i in range(0, len(words), max_words):
                out.append(" ".join(words[i:i + max_words]))
            continue
        if cur and len(" ".join(cur).split()) + len(words) > max_words:
            out.append(" ".join(cur))
            cur = []
        cur.append(sentence)
    if cur:
        out.append(" ".join(cur))
    return out


def _overlap_tail(text: str, overlap_words: int) -> str:
    tail: list[str] = []
    for sentence in reversed(_sentences(text)):
        if len(" ".join(tail + [sentence]).split()) > overlap_words:
            break
        tail.insert(0, sentence)
    return " ".join(tail)


def chunk_structure(blocks: list[Block], max_words: int = 220, overlap_words: int = 40,
                    min_words: int = 12) -> list[Chunk]:
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    pages: list[int] = []

    def section() -> str:
        return " > ".join(title for _, title in stack)

    def emit() -> None:
        if not buf:
            return
        text = " ".join(buf).strip()
        if chunks and len(text.split()) < min_words and chunks[-1].section_path == section():
            chunks[-1].text += " " + text  # fold a tiny remainder into its predecessor
            chunks[-1].page_end = max(chunks[-1].page_end, max(pages))
        else:
            chunks.append(Chunk(len(chunks), text, section(), min(pages), max(pages)))
        buf.clear()
        pages.clear()

    for block in blocks:
        if block.kind == "heading":
            emit()
            while stack and stack[-1][0] >= block.level:
                stack.pop()
            stack.append((block.level, block.text))
            continue
        for piece in _split_long(block.text, max_words):
            words = len(piece.split())
            if buf and len(" ".join(buf).split()) + words > max_words:
                previous = " ".join(buf)
                emit()
                tail = _overlap_tail(previous, overlap_words)
                # Overlap is extra context on top of the chunk budget (chunk <= max_words + overlap_words).
                if tail and len(tail.split()) + words <= max_words + overlap_words:
                    buf.append(tail)
                    pages.append(block.page)
            buf.append(piece)
            pages.append(block.page)
    emit()
    for i, c in enumerate(chunks):
        c.index = i
    return chunks


def chunk_fixed(parsed: ParsedDocument, max_words: int = 220, overlap_words: int = 40) -> list[Chunk]:
    words: list[tuple[str, int]] = [(w, p.number) for p in parsed.pages for w in p.text.split()]
    step = max(1, max_words - overlap_words)
    chunks = []
    for start in range(0, max(1, len(words)), step):
        window = words[start:start + max_words]
        if not window:
            break
        chunks.append(Chunk(len(chunks), " ".join(w for w, _ in window), "", window[0][1], window[-1][1]))
        if start + max_words >= len(words):
            break
    return chunks


def chunk_document(parsed: ParsedDocument, strategy: str = "structure", max_words: int = 220,
                   overlap_words: int = 40) -> list[Chunk]:
    if strategy == "fixed":
        return chunk_fixed(parsed, max_words, overlap_words)
    return chunk_structure(detect_blocks(parsed), max_words, overlap_words)
