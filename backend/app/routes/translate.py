from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.translation_service import translate_text

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    target_lang: str


@router.post("/")
async def translate(payload: TranslateRequest):
    try:
        translated = translate_text(payload.text, payload.target_lang)
        return {"translated_text": translated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
