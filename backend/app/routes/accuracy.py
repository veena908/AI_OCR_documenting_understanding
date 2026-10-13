from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.accuracy_service import evaluate_against_reference

router = APIRouter()

# Edit distance is O(n*m) in pure Python; this keeps an evaluation to a few
# seconds while still covering a typical one- or two-page document.
MAX_REFERENCE_CHARS = 6000


class EvaluateRequest(BaseModel):
    reference_text: str
    extracted_text: str
    corrected_text: str


# Plain "def" (not async): FastAPI runs it in a worker thread, so a slow
# evaluation doesn't block other requests.
@router.post("/evaluate")
def evaluate(payload: EvaluateRequest):
    if not payload.reference_text.strip():
        raise HTTPException(status_code=400, detail="Reference text is empty.")
    if max(len(payload.reference_text), len(payload.extracted_text), len(payload.corrected_text)) > MAX_REFERENCE_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long to evaluate (limit {MAX_REFERENCE_CHARS} characters). Try a single page.",
        )

    return evaluate_against_reference(payload.reference_text, payload.extracted_text, payload.corrected_text)
