import os

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.translation_service import translate_text
from app.services.tts_service import synthesize_speech

router = APIRouter()

_MEDIA_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}


class TtsRequest(BaseModel):
    text: str
    lang: str = "en"


@router.post("/")
async def text_to_speech(payload: TtsRequest, background_tasks: BackgroundTasks):
    try:
        # The document text is assumed English -- speaking it in another
        # language means translating it first, same as the Translate panel.
        text = payload.text if payload.lang == "en" else translate_text(payload.text, payload.lang, source_lang="en")

        audio_path, audio_format = synthesize_speech(text, payload.lang)
        background_tasks.add_task(os.remove, audio_path)

        return FileResponse(
            audio_path,
            media_type=_MEDIA_TYPES[audio_format],
            filename=f"speech.{audio_format}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
