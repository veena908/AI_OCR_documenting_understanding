import os
import re

import numpy as np
import pymupdf
from docx import Document
from PIL import Image, ImageDraw, ImageOps

from app.services.document_loader_service import IMAGE_EXTENSIONS, MIN_PDF_TEXT_CHARS, PDF_RENDER_DPI

# Produces a redacted copy of the *original* uploaded file in its own format
# (PDF stays PDF, photo stays photo, Word stays Word) so the layout the user
# shares is unchanged -- only the sensitive values are blacked out.

BLOCK_CHAR = "█"
OUTPUT_FOLDER = "outputs"

# OCR word boxes shorter than this are only blacked out when they fully
# contain a sensitive value -- otherwise a lone "no" or "of" box would match
# inside almost any name and get redacted by accident.
MIN_PARTIAL_BOX_CHARS = 4


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def _value_pattern(value: str) -> re.Pattern:
    # OCR/correction may differ from the file in spacing and case only.
    return re.compile(r"\s+".join(re.escape(tok) for tok in value.split()), re.IGNORECASE)


def _block(match: re.Match) -> str:
    return "".join(ch if ch.isspace() else BLOCK_CHAR for ch in match.group(0))


# ---------------------------------------------------------------- images

def _ocr_boxes(image: Image.Image) -> list[tuple[tuple[float, float, float, float], str]]:
    # Imported lazily: loading EasyOCR is only needed for image/scanned input.
    from app.services.ocr_service import reader, DETECTION_CANVAS_SIZE

    results = reader.readtext(np.array(image), detail=1, paragraph=False, canvas_size=DETECTION_CANVAS_SIZE)
    boxes = []
    for bbox, text, _conf in results:
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        boxes.append(((min(xs), min(ys), max(xs), max(ys)), text))
    return boxes


def _image_regions(image: Image.Image, values: list[str]) -> tuple[list[tuple[float, float, float, float]], set[str]]:
    """Returns pixel rectangles to black out, and which values were found."""
    regions = []
    found = set()
    targets = [(v, _normalize(v)) for v in values if _normalize(v)]

    for (x0, y0, x1, y1), text in _ocr_boxes(image):
        box_norm = _normalize(text)
        if not box_norm:
            continue

        for value, value_norm in targets:
            idx = box_norm.find(value_norm)
            if idx >= 0:
                # Box like "Name: AKUTHOTA VEENA" -- cover only the value's
                # share of the box width, keeping the label readable.
                width = x1 - x0
                start = x0 + width * idx / len(box_norm)
                end = x0 + width * (idx + len(value_norm)) / len(box_norm)
                regions.append((start, y0, end, y1))
                found.add(value)
            elif len(box_norm) >= MIN_PARTIAL_BOX_CHARS and box_norm in value_norm:
                # Value split across several OCR boxes ("2345" "6789" "0124").
                regions.append((x0, y0, x1, y1))
                found.add(value)

    return regions, found


def _redact_image(src: str, dst: str, values: list[str]) -> set[str]:
    image = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    regions, found = _image_regions(image, values)

    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in regions:
        draw.rectangle((x0 - 2, y0 - 2, x1 + 2, y1 + 2), fill="black")

    image.save(dst)
    return found


# ---------------------------------------------------------------- PDF

def _redact_pdf(src: str, dst: str, values: list[str]) -> set[str]:
    found = set()
    doc = pymupdf.open(src)

    try:
        for page in doc:
            if len(page.get_text().strip()) >= MIN_PDF_TEXT_CHARS:
                for value in values:
                    rects = page.search_for(value)
                    if rects:
                        found.add(value)
                    for rect in rects:
                        page.add_redact_annot(rect, fill=(0, 0, 0))
            else:
                # Scanned page: locate values with OCR on a rendering of the
                # page, then map pixel boxes back to PDF coordinates.
                pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                regions, page_found = _image_regions(image, values)
                found |= page_found
                scale = 72 / PDF_RENDER_DPI
                for x0, y0, x1, y1 in regions:
                    rect = pymupdf.Rect(x0 * scale, y0 * scale, x1 * scale, y1 * scale) + (-1, -1, 1, 1)
                    page.add_redact_annot(rect, fill=(0, 0, 0))

            # Removes the underlying text/pixels, not just draws a box on top,
            # so the value can't be recovered by copy-paste or editing.
            page.apply_redactions()

        doc.save(dst, garbage=4, deflate=True)
    finally:
        doc.close()

    return found


# ---------------------------------------------------------------- DOCX

def _iter_paragraphs(container):
    for paragraph in container.paragraphs:
        yield paragraph
    for table in getattr(container, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_paragraphs(cell)


def _redact_paragraph(paragraph, patterns: list[tuple[str, re.Pattern]], found: set[str]) -> None:
    for value, pattern in patterns:
        if not pattern.search(paragraph.text):
            continue
        found.add(value)

        # Replace inside individual runs first, keeping each run's formatting.
        for run in paragraph.runs:
            run.text = pattern.sub(_block, run.text)

        # Value split across runs (e.g. part bold): fold the paragraph's text
        # into its first run so the value can still be replaced.
        if pattern.search(paragraph.text) and paragraph.runs:
            full = pattern.sub(_block, paragraph.text)
            paragraph.runs[0].text = full
            for run in paragraph.runs[1:]:
                run.text = ""


def _redact_docx(src: str, dst: str, values: list[str]) -> set[str]:
    found = set()
    patterns = [(v, _value_pattern(v)) for v in values]
    doc = Document(src)

    containers = [doc]
    for section in doc.sections:
        containers += [section.header, section.footer]

    for container in containers:
        for paragraph in _iter_paragraphs(container):
            _redact_paragraph(paragraph, patterns, found)

    doc.save(dst)
    return found


# ---------------------------------------------------------------- TXT

def _redact_txt(src: str, dst: str, values: list[str]) -> set[str]:
    with open(src, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    found = set()
    for value in values:
        text, count = _value_pattern(value).subn(_block, text)
        if count:
            found.add(value)

    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    return found


def redact_file(src: str, values: list[str]) -> tuple[str, list[str]]:
    """Writes a redacted copy of src next to the other outputs. Returns the
    output path and the values that could not be located in the file."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    stem, ext = os.path.splitext(os.path.basename(src))
    ext = ext.lower()
    dst = os.path.join(OUTPUT_FOLDER, f"{stem}_redacted{ext}")

    # Longest first, so a full value is redacted before any shorter value
    # that happens to be a part of it.
    values = sorted({v.strip() for v in values if v and v.strip()}, key=len, reverse=True)

    if ext in IMAGE_EXTENSIONS:
        found = _redact_image(src, dst, values)
    elif ext == ".pdf":
        found = _redact_pdf(src, dst, values)
    elif ext == ".docx":
        found = _redact_docx(src, dst, values)
    elif ext == ".txt":
        found = _redact_txt(src, dst, values)
    else:
        raise ValueError(f"Unsupported file format: {ext or 'unknown'}")

    return dst, [v for v in values if v not in found]
