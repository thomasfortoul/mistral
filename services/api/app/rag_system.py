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
                chunk_id = f"{doc_id}_{i}"
                chunks.append(Chunk(id=chunk_id, doc_id=doc_id, title=title, text=part))

        if not chunks:
            raise ValueError(f"No chunks found in {data_dir}")

        print(f"Embedding {len(chunks)} chunks...")
        embeddings: List[List[float]] = []
        for chunk in chunks:
            emb = self._get_text_embedding(chunk.text)
            embeddings.append(emb)

        embeddings_np = np.array(embeddings, dtype=np.float32)
        dim = embeddings_np.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings_np)

        self._chunks = chunks
        self._index = index
        self._dim = dim

        self.save()

    # -------- Persistence --------

    def save(self) -> None:
        if self._index is None or not self._chunks:
            raise RuntimeError("No index or chunks to save")

        faiss_path = self.index_dir / "faiss.index"
        faiss.write_index(self._index, str(faiss_path))

        chunks_data = [
            {"id": c.id, "doc_id": c.doc_id, "title": c.title, "text": c.text}
            for c in self._chunks
        ]
        chunks_path = self.index_dir / "chunks.json"
        chunks_path.write_text(json.dumps(chunks_data, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Saved FAISS index and chunks to {self.index_dir}")

    def load(self) -> None:
        faiss_path = self.index_dir / "faiss.index"
        chunks_path = self.index_dir / "chunks.json"

        if not faiss_path.exists() or not chunks_path.exists():
            raise RuntimeError(
                f"Index not found in {self.index_dir}. Run ingest first."
            )

        self._index = faiss.read_index(str(faiss_path))
        self._dim = self._index.d

        chunks_data = json.loads(chunks_path.read_text(encoding="utf-8"))
        self._chunks = [
            Chunk(id=c["id"], doc_id=c["doc_id"], title=c["title"], text=c["text"])
            for c in chunks_data
        ]

        print(f"Loaded {len(self._chunks)} chunks from {self.index_dir}")

    # -------- Retrieval --------

    def retrieve(self, query: str, k: int = 5) -> List[RetrievedChunk]:
        if self._index is None or not self._chunks:
            raise RuntimeError("Index not loaded. Call load() first.")

        q_emb = np.array([self._get_text_embedding(query)], dtype=np.float32)
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

        chat_response = self.client.chat.complete(
            model=self.chat_model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = chat_response.choices[0].message.content

        return {
            "answer": text,
            "citations": self.format_citations(retrieved),
        }
