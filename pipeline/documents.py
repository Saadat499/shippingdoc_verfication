"""
Turns any attachment (txt/pdf/docx/xlsx) into a flat list of "label: value"
style lines, so extract_rules.py only ever has to deal with one shape.

Returns (lines, doc_title, readable). If readable is False, the caller should
treat the document as unreadable (scanned PDF with nothing extractable, or a
genuinely corrupt file) and escalate to NEEDS_REVIEW / unreadable.

AI engineer: this is the natural place to plug in OCR or Gemini-vision for
scanned PDFs (readable=False cases) — see the TODO below.
"""
from __future__ import annotations

from pathlib import Path


def read_document(path: str, raw_bytes: bytes) -> tuple[list[str], str, bool]:
    ext = Path(path).suffix.lower()
    try:
        if ext == ".txt":
            return _read_txt(raw_bytes)
        if ext == ".pdf":
            return _read_pdf(raw_bytes)
        if ext == ".docx":
            return _read_docx(raw_bytes)
        if ext == ".xlsx":
            return _read_xlsx(raw_bytes)
    except Exception:
        return [], "", False
    return [], "", False


def _read_txt(raw: bytes) -> tuple[list[str], str, bool]:
    text = raw.decode("utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0] if lines else ""
    return lines, title, True


def _read_pdf(raw: bytes) -> tuple[list[str], str, bool]:
    import io
    import pdfplumber

    def _to_lines(text: str) -> list[str]:
        return [l.strip() for l in text.splitlines() if l.strip()]

    lines: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                lines.extend(_to_lines(page.extract_text(use_text_flow=True) or ""))
    except Exception:
        # pdfplumber can't open damaged files (e.g. truncated / bad xref).
        # pypdf in non-strict mode can often still recover the text.
        lines = []
        try:
            from pypdf import PdfReader
            for page in PdfReader(io.BytesIO(raw), strict=False).pages:
                lines.extend(_to_lines(page.extract_text() or ""))
        except Exception:
            return [], "", False   # truly unrecoverable -> unreadable

    if not lines:
        # No extractable text layer -> likely a scanned/image-only PDF.
        # TODO(AI engineer): try OCR (pytesseract on a rasterized page) or
        # Gemini vision here before giving up. For now: unreadable.
        return [], "", False
    title = lines[0]
    return lines, title, True


def _read_docx(raw: bytes) -> tuple[list[str], str, bool]:
    import io
    import docx

    d = docx.Document(io.BytesIO(raw))
    lines = [p.text.strip() for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            # a cell can itself contain multiple paragraphs joined by "\n"
            # (e.g. a multi-line address) — flatten those so each table row
            # is exactly one line, or the label regex below never matches.
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            if any(cells):
                lines.append(": ".join(cells) if len(cells) == 2 else " | ".join(cells))
    if not lines:
        return [], "", False
    title = lines[0]
    return lines, title, True


def _read_xlsx(raw: bytes) -> tuple[list[str], str, bool]:
    import io
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if len(cells) >= 2:
                lines.append(": ".join(cells[:2]))
            elif len(cells) == 1:
                lines.append(cells[0])
    if not lines:
        return [], "", False
    title = lines[0]
    return lines, title, True
