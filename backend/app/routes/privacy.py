import mimetypes
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.routes.upload import UPLOAD_FOLDER
from app.services.redaction_service import redact_file

router = APIRouter()


class RedactRequest(BaseModel):
    filename: str
    values: list[str]


@router.post("/redact")
async def redact_document(payload: RedactRequest, background_tasks: BackgroundTasks):
    # basename() keeps the request from reaching files outside uploads/.
    src = os.path.join(UPLOAD_FOLDER, os.path.basename(payload.filename))

    if not os.path.isfile(src):
        raise HTTPException(status_code=404, detail="Original file not found. Please re-upload it.")

    try:
        path, missed = redact_file(src, payload.values)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    background_tasks.add_task(os.remove, path)

    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path)[0] or "application/octet-stream",
        filename=os.path.basename(path),
        headers={"X-Redaction-Missed": str(len(missed))},
    )
