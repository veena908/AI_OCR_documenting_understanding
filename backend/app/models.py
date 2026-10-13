from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.database import Base


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String(255), nullable=False)

    filepath = Column(String(500), nullable=False)

    document_type = Column(String(100), default="Unknown")

    extracted_text = Column(Text)

    corrected_text = Column(Text)

    summary = Column(Text)

    language = Column(String(50), default="English")

    upload_time = Column(DateTime, default=datetime.utcnow)

    status = Column(String(50), default="Uploaded")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer)

    question = Column(Text)

    answer = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)