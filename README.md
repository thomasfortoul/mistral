# Mistral RAG Chat

A polished RAG (Retrieval-Augmented Generation) system built with FastAPI and Mistral AI that answers questions using grounded retrieval over markdown documents.

## About This Project

This is the Mistral Internship Project application that implements a production-ready RAG pipeline following Mistral's official quickstart pattern:
- Load and chunk markdown documents from `/data`
- Create embeddings with Mistral's `mistral-embed` model
- Index embeddings in FAISS (`IndexFlatL2`)
- Retrieve relevant chunks for queries
- Generate grounded answers with Mistral's chat completion API
- Return answers with citations

## Features

- ✅ Simple fixed-size chunking with overlap (2048 chars, 200 overlap)
- ✅ FAISS-based vector search for fast retrieval
- ✅ Context-grounded prompting (mirrors Mistral quickstart)
- ✅ Citation tracking and preview
- ✅ Clean separation: `rag_system.py` (RAG logic) + `main.py` (FastAPI routes)

## Setup

### Prerequisites

- Python 3.9+
- Mistral API key

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd mistral
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set your Mistral API key:
```bash
export MISTRAL_API_KEY="your-api-key-here"
```

4. Build the index:
```bash
python scripts/ingest.py
```

This will:
- Load all `*.md` files from `data/`
- Chunk them into ~2048 character segments with 200 char overlap
- Create embeddings using `mistral-embed`
- Build a FAISS index and save to `storage/`

5. Start the API server:
```bash
uvicorn services.api.app.main:app --reload --port 8000
```

## Usage

### API Endpoint

**POST** `/chat`

Request:
```json
{
  "question": "What are the key requirements for this role?",
  "top_k": 5
}
```

Response:
```json
{
  "answer": "Based on the context provided...",
  "citations": [
    {
      "chunk_id": "job_description_0",
      "doc_id": "job_description",
      "title": "job_description.md",
      "distance": 0.234,
      "preview": "The role requires strong full-stack development skills..."
    }
  ]
}
```

### Example with curl

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What technologies should I know?", "top_k": 5}'
```

## Architecture

### Directory Structure

```
mistral/
├── services/
│   └── api/
│       └── app/
│           ├── __init__.py
│           ├── main.py          # FastAPI routes
│           └── rag_system.py    # RAG logic (Mistral + FAISS)
├── scripts/
│   └── ingest.py                # Index builder
├── data/                         # Your .md files go here
├── storage/                      # FAISS index + chunks.json
├── requirements.txt
└── README.md
```

### How RAG Works

1. **Ingestion** (`scripts/ingest.py`):
   - Loads all `*.md` files from `data/`
   - Chunks text into fixed-size segments
   - Calls Mistral embeddings API (`mistral-embed`)
   - Builds FAISS `IndexFlatL2`
   - Persists `faiss.index` + `chunks.json` to `storage/`

2. **Query** (`POST /chat`):
   - Embeds user question with `mistral-embed`
   - Retrieves top-K chunks via FAISS search
   - Builds context-grounded prompt
   - Calls Mistral chat completion API
   - Returns answer + citations

### Design Tradeoffs

**Why FastAPI?**
- Async-native for streaming responses
- Built-in OpenAPI docs
- Easy to test and extend

**Why FAISS?**
- Fast local vector search
- No external database dependencies
- Simple persistence (single file)
- Recommended in Mistral quickstart

**Why separate `rag_system.py`?**
- Clean separation of concerns
- Testable RAG logic independent of web framework
- Easy to swap FastAPI for another framework

## Environment Variables

Create a .env file in the root directory with the following variables:
- `MISTRAL_API_KEY` (required): Your Mistral API key
- `MISTRAL_CHAT_MODEL` (optional): Chat model to use (default: `mistral-large-latest`)
- `RAG_INDEX_DIR` (optional): Directory for FAISS index (default: `storage`)

sample:
```bash
MISTRAL_API_KEY= your-api-key-here
MISTRAL_CHAT_MODEL=mistral-small-latest
RAG_INDEX_DIR=storage
```

## License

MIT

---

Thanks for looking this over. Really looking forward to the next steps.
