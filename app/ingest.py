"""Turn an HR policy PDF into section-aware, citable chunks."""
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader

from .config import CHUNK_OVERLAP, CHUNK_SIZE, CHUNKS_PATH

# "5. Leave Policy", "5.1 Sandwich Rule", "Annexure A: Quick Reference FAQ"
HEADING_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})?)\.?\s+([A-Z][^\n]{2,80})$")
ANNEXURE_RE = re.compile(r"^\s*(Annexure\s+[A-Z][^\n]{0,80})$")
FOOTER_RE = re.compile(r"^(XYZ Technologies Pvt\. Ltd\..*Internal|Page \d+)\s*$", re.I)


@dataclass
class Chunk:
    id: int
    text: str
    section: str
    page: int
    source: str


def _clean_lines(raw: str) -> list[str]:
    lines = []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line.strip() or FOOTER_RE.match(line.strip()):
            continue
        lines.append(line)
    return lines


def _split(text: str, size: int, overlap: int) -> list[str]:
    """Split on paragraph boundaries, packing up to `size` characters."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[\u2022\-\*] )", text) if p.strip()]
    out, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) + 1 > size:
            out.append(buf.strip())
            buf = (buf[-overlap:] + "\n" + p) if overlap else p
        else:
            buf = f"{buf}\n{p}" if buf else p
    if buf.strip():
        out.append(buf.strip())
    return out or [text.strip()]


def parse_pdf(pdf_path: Path) -> list[Chunk]:
    reader = PdfReader(str(pdf_path))
    source = pdf_path.name

    # Pass 1: collect (section_title, page, line) for every line in reading order.
    current = "Front Matter"
    records: list[tuple[str, int, str]] = []
    for page_no, page in enumerate(reader.pages, start=1):
        for line in _clean_lines(page.extract_text() or ""):
            stripped = line.strip()
            m = HEADING_RE.match(stripped)
            a = ANNEXURE_RE.match(stripped)
            if a:
                current = a.group(1).strip()
                continue
            if m and not stripped.endswith((",", ";")):
                current = f"Section {m.group(1)} — {m.group(2).strip()}"
                continue
            records.append((current, page_no, line))

    # Pass 2: group consecutive lines by section, remembering the first page seen.
    grouped: list[tuple[str, int, list[str]]] = []
    for section, page_no, line in records:
        if grouped and grouped[-1][0] == section:
            grouped[-1][2].append(line)
        else:
            grouped.append((section, page_no, [line]))

    chunks: list[Chunk] = []
    for section, page_no, lines in grouped:
        body = "\n".join(lines).strip()
        if len(body) < 40:
            continue
        for piece in _split(body, CHUNK_SIZE, CHUNK_OVERLAP):
            # Prefix the heading so the embedding carries topical context.
            chunks.append(
                Chunk(
                    id=len(chunks),
                    text=f"{section}\n\n{piece}",
                    section=section,
                    page=page_no,
                    source=source,
                )
            )
    return chunks


def save_chunks(chunks: list[Chunk]) -> None:
    CHUNKS_PATH.write_text(
        json.dumps([asdict(c) for c in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_chunks() -> list[Chunk]:
    if not CHUNKS_PATH.exists():
        return []
    return [Chunk(**d) for d in json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))]
