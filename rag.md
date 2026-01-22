## 1) Updated project scope (aligned to Mistral RAG quickstart)

### RAG pipeline (exactly the quickstart flow)

1. **Load documents** (your `data/*.md` files)
2. **Split into chunks** (quickstart shows simple fixed-size chunking, e.g. 2048 characters) 
3. **Create embeddings** with Mistral embeddings API using model **`mistral-embed`** 
4. **Index embeddings** in **FAISS** (`IndexFlatL2`) 
5. For a user query:

   * embed the query with **`mistral-embed`** 
   * retrieve Top-K via `index.search()` 
6. **Prompt assembly**: include retrieved chunks as “Context information is below…” and instruct “Given the context information and not prior knowledge…” 
7. **Generate answer** with Mistral chat completion (quickstart uses `client.chat.complete`) 

### Implementation requirement

* Backend has **two files**:

  * `main.py` = FastAPI routes only
  * `rag_system.py` = all RAG logic (ingest, embed, index, retrieve, prompt build)

---

## 2) “Second implementation file” — `rag_system.py` (RAG-only)

This file follows the Mistral quickstart pattern: `Mistral(api_key=...)`, `client.embeddings.create(model="mistral-embed", ...)`, FAISS `IndexFlatL2`, and `index.search(...)`. 

```python
# services/api/app/rag_system.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import faiss
from mistralai import Mistral

# -----------------------------
# Data structures
# -----------------------------

@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    title: str
    text: str

@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    distance: float


# -----------------------------
# RAG System (Mistral + FAISS)
# -----------------------------

class RAGSystem:
    """
    Minimal RAG system aligned with Mistral's RAG quickstart:
    - chunk text
    - embed with model="mistral-embed"
    - store/search embeddings in FAISS IndexFlatL2
    - build a context-grounded prompt
    """
    def __init__(
        self,
        api_key: str,
        embedding_model: str = "mistral-embed",
        chat_model: str = "mistral-large-latest",
        index_dir: str = "storage",
    ) -> None:
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is required")

        self.client = Mistral(api_key=api_key)
        self.embedding_model = embedding_model
        self.chat_model = chat_model

        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self._chunks: List[Chunk] = []
        self._index: Optional[faiss.Index] = None
        self._dim: Optional[int] = None

    # -------- Embeddings (Mistral) --------

    def _get_text_embedding(self, text: str) -> List[float]:
        # Mirrors the quickstart embeddings call:
        # client.embeddings.create(model="mistral-embed", inputs=input)
        resp = self.client.embeddings.create(
            model=self.embedding_model,
            inputs=text,
        )
        return resp.data[0].embedding

    # -------- Chunking --------

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 2048, overlap: int = 200) -> List[str]:
        """
        Quickstart shows simple fixed-size chunking by characters (2048 chars).
        We add overlap to improve recall.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")

        chunks: List[str] = []
        start = 0
        n = len(text)

        while start < n:
            end = min(start + chunk_size, n)
            chunks.append(text[start:end])
            if end == n:
                break
            start = end - overlap

        return chunks

    # -------- Ingest / Build Index --------

    def ingest_markdown_files(
        self,
        data_dir: str = "data",
        chunk_size: int = 2048,
        overlap: int = 200,
    ) -> None:
        """
        Loads *.md from data_dir, chunks, embeds, and builds FAISS index.
        Persists:
          - storage/faiss.index
          - storage/chunks.json
        """
        data_path = Path(data_dir)
        if not data_path.exists():
            raise FileNotFoundError(f"Data dir not found: {data_dir}")

        chunks: List[Chunk] = []
        for md_path in sorted(data_path.glob("*.md")):
            doc_id = md_path.stem
            title = md_path.name
            text = md_path.read_text(encoding="utf-8")

            parts = self.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            for i, part in enumerate(parts):
                chunks.append(
                    Chunk(
                        id=f"{doc_id}::{i}",
                        doc_id=doc_id,
                        title=title,
                        text=part,
                    )
                )

        if not chunks:
            raise ValueError(f"No markdown files found in {data_dir}")

        # Embed all chunks with Mistral embeddings
        embeddings = np.array([self._get_text_embedding(c.text) for c in chunks], dtype="float32")

        # Build FAISS index (IndexFlatL2) as in quickstart
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)

        self._chunks = chunks
        self._index = index
        self._dim = dim

        self._persist()

    def load(self) -> bool:
        """
        Loads index + chunks from disk if present.
        Returns True if loaded, False if not found.
        """
        idx_path = self.index_dir / "faiss.index"
        chunks_path = self.index_dir / "chunks.json"
        meta_path = self.index_dir / "meta.json"

        if not (idx_path.exists() and chunks_path.exists() and meta_path.exists()):
            return False

        self._index = faiss.read_index(str(idx_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self._dim = int(meta["dim"])

        raw_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        self._chunks = [Chunk(**c) for c in raw_chunks]
        return True

    def _persist(self) -> None:
        if self._index is None or self._dim is None:
            raise RuntimeError("Index not built")

        idx_path = self.index_dir / "faiss.index"
        chunks_path = self.index_dir / "chunks.json"
        meta_path = self.index_dir / "meta.json"

        faiss.write_index(self._index, str(idx_path))
        chunks_path.write_text(json.dumps([c.__dict__ for c in self._chunks], indent=2), encoding="utf-8")
        meta_path.write_text(json.dumps({"dim": self._dim}, indent=2), encoding="utf-8")

    # -------- Retrieval --------

    def retrieve(self, query: str, k: int = 5) -> List[RetrievedChunk]:
        if self._index is None or not self._chunks:
            raise RuntimeError("RAG index not loaded/built. Run ingest or load().")

        q_emb = np.array([self._get_text_embedding(query)], dtype="float32")
        distances, indices = self._index.search(q_emb, k=k)

        results: List[RetrievedChunk] = []
        for dist, idx in zip(distances[0].tolist(), indices[0].tolist()):
            if idx < 0 or idx >= len(self._chunks):
                continue
            results.append(RetrievedChunk(chunk=self._chunks[idx], distance=float(dist)))
        return results

    # -------- Prompting --------

    @staticmethod
    def build_prompt(retrieved: List[RetrievedChunk], question: str) -> str:
        """
        Mirrors the quickstart prompt style:
        "Context information is below... Given the context information and not prior knowledge..."
        """
        ctx_blocks = []
        for r in retrieved:
            ctx_blocks.append(
                f"[{r.chunk.id} | {r.chunk.title}]\n{r.chunk.text}"
            )
        ctx = "\n\n".join(ctx_blocks)

        prompt = f"""
Context information is below.
---------------------
{ctx}
---------------------
Given the context information and not prior knowledge, answer the query.
Query: {question}
Answer:
""".strip()
        return prompt

    @staticmethod
    def format_citations(retrieved: List[RetrievedChunk]) -> List[Dict[str, Any]]:
        """
        Structured citations for the frontend.
        """
        citations = []
        for r in retrieved:
            citations.append(
                {
                    "chunk_id": r.chunk.id,
                    "doc_id": r.chunk.doc_id,
                    "title": r.chunk.title,
                    "distance": r.distance,
                    "preview": r.chunk.text[:240],
                }
            )
        return citations

    # -------- Generation (Mistral chat) --------

    def answer(self, question: str, k: int = 5) -> Dict[str, Any]:
        retrieved = self.retrieve(question, k=k)
        prompt = self.build_prompt(retrieved, question)

        # Quickstart uses client.chat.complete(...)
        chat_response = self.client.chat.complete(
            model=self.chat_model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = chat_response.choices[0].message.content

        return {
            "answer": text,
            "citations": self.format_citations(retrieved),
        }
```

---

## 3) Thin FastAPI wrapper — `main.py`

```python
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
    # If index doesn't exist, the API can still start,
    # but /chat will fail until you ingest.
    rag.load()

@app.post("/chat")
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    try:
        return rag.answer(req.question, k=req.top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
```

---

## 4) Minimal ingestion script (so reviewers can build the index)

```python
# scripts/ingest.py
import os
from services.api.app.rag_system import RAGSystem

if __name__ == "__main__":
    rag = RAGSystem(
        api_key=os.environ.get("MISTRAL_API_KEY", ""),
        embedding_model="mistral-embed",
        chat_model=os.environ.get("MISTRAL_CHAT_MODEL", "mistral-large-latest"),
        index_dir=os.environ.get("RAG_INDEX_DIR", "storage"),
    )
    rag.ingest_markdown_files(data_dir="data", chunk_size=2048, overlap=200)
    print("✅ Ingest complete. Index saved to storage/")
```

---

## 5) requirements.txt (backend)

```txt
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.0
numpy>=1.24
faiss-cpu>=1.7.4
mistralai>=1.0.0
```

---

### Notes tying directly to the Mistral quickstart

* Uses **`mistral-embed`** for embeddings exactly like the doc. 
* Uses **FAISS `IndexFlatL2`** and `index.search(...)` like the doc. 
* Uses the same **prompt structure** (“Context information is below… Given the context information and not prior knowledge…”) and **`client.chat.complete`** pattern. 
