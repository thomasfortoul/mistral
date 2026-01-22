# services/api/app/main.py
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .rag_system import RAGSystem

app = FastAPI(
    title="HireMeGPT API",
    description="Mistral RAG-powered chat API for Thomas Fortoul's internship application",
    version="1.0.0"
)

# Mount static files
static_dir = Path(__file__).parent.parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class ChatRequest(BaseModel):
    question: str
    top_k: int = 5

rag = RAGSystem(
    api_key=os.environ.get("MISTRAL_API_KEY", ""),
    embedding_model="mistral-embed",
    chat_model=os.environ.get("MISTRAL_CHAT_MODEL", "mistral-large-latest"),
    index_dir=os.environ.get("RAG_INDEX_DIR", "storage"),
)

@app.on_event("startup")
def _load_or_warn():
    try:
        rag.load()
    except RuntimeError:
        print("⚠️  Index not loaded. Run 'python scripts/ingest.py' first.")

@app.get("/")
def root():
    """Serve the chat interface"""
    static_file = Path(__file__).parent.parent.parent.parent / "static" / "index.html"
    if static_file.exists():
        return FileResponse(static_file)
    return {
        "message": "HireMeGPT API - Mistral RAG Chat",
        "endpoints": {
            "POST /chat": "Ask questions about Thomas Fortoul's internship application",
            "GET /docs": "Interactive API documentation",
            "GET /health": "Health check"
        },
        "example": {
            "method": "POST",
            "url": "/chat",
            "body": {
                "question": "Why is Thomas a good fit for the Mistral internship?",
                "top_k": 5
            }
        }
    }

@app.get("/health")
def health():
    return {"status": "healthy", "chunks_loaded": len(rag._chunks)}

@app.post("/chat")
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    try:
        return rag.answer(req.question, k=req.top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
