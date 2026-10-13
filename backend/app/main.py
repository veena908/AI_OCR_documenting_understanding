
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
# Import API routers
from app.routes.upload import router as upload_router
from app.routes.chat import router as chat_router
from app.routes.export import router as export_router
from app.routes.translate import router as translate_router
from app.routes.tts import router as tts_router
from app.routes.privacy import router as privacy_router
from app.routes.accuracy import router as accuracy_router

app = FastAPI(
    title="AI OCR Document Understanding API",
    description="AI-powered OCR system with document understanding, translation, summarization, and chatbot.",
    version="1.0.0"
)

# Enable CORS (allows React frontend to communicate with FastAPI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Redaction-Missed"],
)

# Register API routes
app.include_router(upload_router, prefix="/upload", tags=["Upload"])
app.include_router(chat_router, prefix="/chat", tags=["Chat"])
app.include_router(export_router, prefix="/export", tags=["Export"])
app.include_router(translate_router, prefix="/translate", tags=["Translate"])
app.include_router(tts_router, prefix="/tts", tags=["Text-to-Speech"])
app.include_router(privacy_router, prefix="/privacy", tags=["Privacy"])
app.include_router(accuracy_router, prefix="/accuracy", tags=["Accuracy"])


@app.get("/")
async def root():
    return {
        "message": "Welcome to AI OCR Document Understanding API",
        "version": "1.0.0",
        "status": "Running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "AI OCR Backend"
    }
