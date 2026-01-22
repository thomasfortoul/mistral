#!/usr/bin/env python3
# scripts/ingest.py
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.api.app.rag_system import RAGSystem

if __name__ == "__main__":
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        print("❌ MISTRAL_API_KEY environment variable not set")
        sys.exit(1)
    
    rag = RAGSystem(
        api_key=api_key,
        embedding_model="mistral-embed",
        chat_model=os.environ.get("MISTRAL_CHAT_MODEL", "mistral-large-latest"),
        index_dir=os.environ.get("RAG_INDEX_DIR", "storage"),
    )
    
    try:
        rag.ingest_markdown_files(data_dir="data", chunk_size=2048, overlap=200)
        print("✅ Ingest complete. Index saved to storage/")
    except Exception as e:
        print(f"❌ Ingest failed: {e}")
        sys.exit(1)
