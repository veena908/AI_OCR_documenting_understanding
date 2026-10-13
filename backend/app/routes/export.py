import os

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.export_service import export_pdf, export_docx, export_xlsx

router = APIRouter()

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

EXPORTERS = {
    "pdf": export_pdf,
    "docx": export_docx,
    "xlsx": export_xlsx,
}


class ExportRequest(BaseModel):
    text: str
    structured_info: dict = {}
    document_type: str = "Unknown"


@router.post("/{export_format}")
async def export_document(export_format: str, payload: ExportRequest, background_tasks: BackgroundTasks):
    if export_format not in EXPORTERS:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    try:
        path = EXPORTERS[export_format](payload.text, payload.structured_info, payload.document_type)
        background_tasks.add_task(os.remove, path)

        return FileResponse(
            path,
            media_type=MEDIA_TYPES[export_format],
            filename=f"document.{export_format}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
