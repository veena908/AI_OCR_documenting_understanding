from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatHistory
from app.services.qa_service import answer_question
from app.services.rag_service import retrieve_relevant_chunks

router = APIRouter()


class ChatRequest(BaseModel):
    document_id: str
    question: str


@router.post("/")
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        context = retrieve_relevant_chunks(payload.document_id, payload.question)

        if not context.strip():
            # Distinguish "this document was never indexed" (upload-time
            # indexing failure, or a stale document_id) from "the answer
            # isn't in the document" -- the latter comes from answer_question
            # itself once real context is available.
            return {"answer": "This document isn't available for chat. Please re-upload it and try again."}

        answer = answer_question(context, payload.question)

        try:
            record = ChatHistory(question=payload.question, answer=answer)
            db.add(record)
            db.commit()
        except Exception:
            db.rollback()

        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
