# services/api/app/main.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .rag_system import RAGSystem

app = FastAPI(title="HireMeGPT API")

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

@app.post("/chat")
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    try:
        return rag.answer(req.question, k=req.top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
