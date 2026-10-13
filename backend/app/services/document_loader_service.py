import os

import pymupdf
from PIL import Image
from docx import Document

from app.services.image_preprocessing import preprocess_image
from app.services.ocr_service import extract_text
from app.services.azure_ocr_service import transcribe_image as azure_transcribe_image
from app.services.vision_ocr_service import transcribe_image as claude_transcribe_image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf", ".docx", ".txt"}

# Below this many characters, a PDF page is treated as scanned/image-based
# (little or no embedded text) and rendered to an image for OCR instead.
MIN_PDF_TEXT_CHARS = 40
PDF_RENDER_DPI = 200


def _ocr_image_path(image_path: str) -> str:
    # Cloud OCR (Azure Read, or Claude vision — whichever has credentials in
    # backend/.env) reads handwriting far more accurately than EasyOCR/TrOCR
    # and in a few seconds instead of the tens of seconds the local models
    # need on CPU. Each returns None when unconfigured or failing.
    for transcribe in (azure_transcribe_image, claude_transcribe_image):
        cloud_text = transcribe(image_path)

        if cloud_text:
            return cloud_text

    processed_path, color_path = preprocess_image(image_path)
    return extract_text(processed_path, color_path)


def _load_image(file_path: str) -> str:
    # Pillow supports far more formats (webp, gif, tiff, ...) than OpenCV's
    # imread, so normalize everything to a plain PNG before handing it to
    # the existing (cv2-based) preprocessing/OCR pipeline.
    normalized_path = file_path + "__normalized.png"
    Image.open(file_path).convert("RGB").save(normalized_path)

    try:
        return _ocr_image_path(normalized_path)
    finally:
        if os.path.exists(normalized_path):
            os.remove(normalized_path)


def _load_pdf(file_path: str) -> str:
    doc = pymupdf.open(file_path)
    pages_text = []

    try:
        for page_number, page in enumerate(doc):
            text = page.get_text().strip()

            if len(text) >= MIN_PDF_TEXT_CHARS:
                pages_text.append(text)
                continue

            # Little/no embedded text -> likely a scanned page; OCR it.
            page_image_path = f"{file_path}__page{page_number}.png"
            page.get_pixmap(dpi=PDF_RENDER_DPI).save(page_image_path)

            try:
                pages_text.append(_ocr_image_path(page_image_path))
            finally:
                if os.path.exists(page_image_path):
                    os.remove(page_image_path)
    finally:
        doc.close()

    return "\n\n".join(pages_text)


def _load_docx(file_path: str) -> str:
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _load_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def is_presentation_file(file_path: str, filename: str) -> bool:
    """A PDF exported from PowerPoint/Slides has landscape pages (16:9 or
    4:3), while resumes, reports, receipts etc. are portrait. Page shape is
    far more reliable than the text for spotting slide decks, whose sparse
    bullet text otherwise matches no document type at all."""
    if os.path.splitext(filename)[1].lower() != ".pdf":
        return False

    with pymupdf.open(file_path) as doc:
        if doc.page_count < 2:
            return False
        landscape = sum(1 for page in doc if page.rect.width > page.rect.height)
        return landscape / doc.page_count > 0.5


def load_document_text(file_path: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        return _load_image(file_path)
    if ext == ".pdf":
        return _load_pdf(file_path)
    if ext == ".docx":
        return _load_docx(file_path)
    if ext == ".txt":
        return _load_txt(file_path)

    raise ValueError(f"Unsupported file format: {ext or 'unknown'}")
