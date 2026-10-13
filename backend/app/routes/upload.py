import logging
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UploadedDocument
from app.services.document_loader_service import load_document_text, is_presentation_file, SUPPORTED_EXTENSIONS
from app.services.correction_service import correct_text_with_report
from app.services.accuracy_service import build_accuracy_report
from app.services.classification_service import classify_document
from app.services.extraction_service import extract_structured_info
from app.services.summarization_service import summarize_text
from app.services.rag_service import index_document
from app.services.privacy_service import detect_sensitive_data

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or 'unknown'}'. "
                   f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    try:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        document_id = str(uuid.uuid4())

        extracted_text = load_document_text(file_path, file.filename)
        corrected_text, correction_report = correct_text_with_report(extracted_text)
        accuracy = build_accuracy_report(extracted_text, corrected_text, correction_report)
        document_type = classify_document(
            corrected_text, is_presentation=is_presentation_file(file_path, file.filename)
        )
        structured_info = extract_structured_info(corrected_text)
        summary = summarize_text(corrected_text)
        privacy = detect_sensitive_data(corrected_text, structured_info["names"])

        try:
            index_document(document_id, corrected_text)
        except Exception:
            # Indexing failure must not fail the whole upload (OCR results
            # are still useful without chat), but swallowing it silently
            # left "ask about this document" permanently broken for any
            # document indexed while Qdrant's local store was locked by
            # another process, with no way to tell why.
            logger.exception("Failed to index document %s for chat/RAG", document_id)

        try:
            record = UploadedDocument(
                filename=file.filename,
                filepath=file_path,
                document_type=document_type,
                extracted_text=extracted_text,
                corrected_text=corrected_text,
                summary=summary,
                status="Processed",
            )
            db.add(record)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "success": True,
            "document_id": document_id,
            "filename": file.filename,
            "extracted_text": extracted_text,
            "corrected_text": corrected_text,
            "document_type": document_type,
            "structured_info": structured_info,
            "summary": summary,
            "privacy": privacy,
            "accuracy": accuracy,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
