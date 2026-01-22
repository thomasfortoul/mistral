Below is a scoped **product document / build spec** for a GitHub project that matches Mistral’s internship prompt (Next.js chat app using their public API + best practices) and showcases exactly the skills they list (full-stack, smooth UX, “chatbot / search / document answering,” and dev-facing tooling).
## 1) Project one-liner

**HireMeGPT (Mistral RAG Chat)** — a polished Next.js chat UI backed by a Python (FastAPI) RAG service that answers: *“Why should you hire Thomas as a Software Engineering Intern at Mistral?”* using grounded retrieval over (1) the Mistral internship job description, (2) a short “What is Mistral” dossier, and (3) your resume + project portfolio notes, with citations.

Why this fits their posting:

* They explicitly suggest **“Chat Application: Next.js with our public API”** and/or a **Python project with FastAPI** 
* Their role includes building **user-facing apps** and **developer-facing tools** like dashboards/evals 
* They emphasize **detailed README** and **easy to test** 

---

## 2) Goals and non-goals

### Goals (what you’ll demo)

1. **A great chat experience** (fast, streaming, good UI) that uses Mistral’s API.
2. **Simple but real RAG**: chunk → embed → retrieve → cite → answer.
3. **“Intern pitch agent” behavior**: consistently produces structured, job-relevant answers (STAR examples, skills mapping, tradeoffs, links to repo work).
4. **Best practices**: clean repo, env vars, linting, tests, docker-compose, good README.
5. **Small dev-facing tool**: an “Eval” page to run canned questions and view groundedness/citations.

### Non-goals (keep scope tight)

* No multi-user auth, no payments, no complex agent orchestration.
* No fancy vector DB ops; keep it local (SQLite/Chroma) or a single file index.
* No heavy document upload UX (optional stretch).

---

## 3) Target user & core use cases

### Primary user

* **Mistral recruiter/engineer** reviewing your repo + running the demo locally.

### Top user stories

1. “I open the app and immediately see who you are + what you built.”
2. “I ask: *Why are you a fit for this internship?* and get a grounded answer with citations.”
3. “I ask technical follow-ups (stack choices, tradeoffs) and it answers consistently.”
4. “I can run tests and understand setup in 5–10 minutes.”

---

## 4) Product requirements

### 4.1 Chat experience (frontend)

**Must-have**

* Next.js chat UI with:

  * message list, markdown rendering, code blocks, copy button
  * streaming tokens
  * “suggested prompts” chips (e.g., “Map my experience to the job requirements”)
* Left sidebar “Profile card”:

  * profile picture
  * short intro + key links (GitHub, LinkedIn, portfolio)
  * “Resume highlights” bullet list
* “Citations drawer” per assistant message (expandable): shows retrieved snippets + source names.

**Nice-to-have**

* Conversation presets: “Recruiter screen,” “Hiring manager deep dive,” “System design Q&A.”
* Theme toggle.

### 4.2 RAG backend behavior (Python FastAPI)

**Must-have**

* `/chat` endpoint: takes conversation + optional mode; returns streamed response.
* Retrieval over a small corpus:

  * `job.md` (the posting content)
  * `mistral_about.md` (your short Mistral dossier)
  * `thomas_resume.md` (curated resume + bullets + portfolio)
* Each answer should:

  * cite sources (doc name + snippet id)
  * refuse or qualify if info isn’t in sources (“I don’t have that in my docs…”)

**Nice-to-have**

* `/eval/run` endpoint to run canned Qs and output JSON metrics (citation coverage, length, latency).

### 4.3 Dev-facing “Eval” page (mini dashboard)

This is your “instrumentation / evaluation interface” nod, aligned with their internship description. 

**Must-have**

* A page that runs 10–15 predefined questions (buttons).
* Displays:

  * model used
  * latency
  * answer text
  * citation count
  * retrieved chunks preview

---

## 5) Data & RAG design (simple, explainable)

### Source documents (versioned in repo)

* `data/job_mistral_intern.md` — copy of the posting text (plus the URL)
* `data/mistral_about.md` — 1–2 pages summarizing Mistral + products + API (with citations/links)
* `data/thomas_profile.md` — your curated narrative:

  * short bio
  * key projects (with links)
  * skills matrix
  * STAR stories
  * “why Mistral specifically” bullets

> The job post explicitly describes the internship focus and desired skills (full-stack/infra, UX quality, building AI solutions with chat/embedding APIs). 

### Chunking & embeddings

* Chunk size: ~600–900 tokens, overlap ~100–150 tokens.
* Store metadata: `{doc_id, title, section, url, chunk_index}`.
* Embeddings:

  * Use Mistral embeddings endpoint if you want to stay “all-Mistral,” or
  * Use a lightweight local embedding model (faster offline dev).

If you want maximum alignment with “chat APIs, embedding APIs,” use Mistral for both chat + embeddings. 

### Retrieval

* Top-K = 4–8 chunks, MMR optional.
* Return chunks + metadata to the prompt.
* Frontend displays citations by chunk.

### Prompting (the “intern pitch agent”)

System-style rules:

* Role: “You are Thomas’s internship application agent.”
* Always ground claims in retrieved context.
* Prefer: **skills mapping → evidence (projects) → relevance (job requirement) → impact**.
* If asked something not in docs: ask for missing info or answer generally but label it.

---

## 6) Mistral API integration (grounded in official docs)

Use the official SDKs:

* **JS/TS:** `@mistralai/mistralai` ([npm][2])
* **Python:** `mistralai` (note the SDK v1 migration warning on PyPI—pin versions) ([PyPI][3])
* Chat endpoint examples and models like `mistral-small-latest` are shown in Mistral’s API specs. ([Mistral AI Documentation][4])

Recommended approach:

* **Python backend calls Mistral** (keeps API key server-side).
* Frontend calls your backend only.

---

## 7) System architecture

### Components

1. **Next.js (Frontend)**

   * Chat UI
   * Eval page
   * Calls FastAPI over HTTP
2. **FastAPI (Backend)**

   * `/chat` streaming endpoint
   * `/retrieve` (optional debug)
   * `/eval/run`
   * RAG pipeline
3. **Vector store**

   * Chroma (local persistent) or FAISS + local files

### Request flow (chat)

User message → FastAPI → retrieve top chunks → compose prompt → call Mistral Chat Completions → stream tokens back → UI renders message + citations.

---

## 8) Repo structure (suggested)

```
hiremegpt-mistral/
  apps/
    web/                  # Next.js
      app/
      components/
      public/profile.jpg
      tests/
  services/
    api/                  # FastAPI
      app/
        main.py
        rag/
        eval/
      tests/
  data/
    job_mistral_intern.md
    mistral_about.md
    thomas_profile.md
  scripts/
    ingest.py             # builds embeddings / index
  docker-compose.yml
  README.md
```

---

## 9) Testing & quality bar (match their “easy to test” ask)

They explicitly want “easy to test” + “detailed README.” 

### Backend tests

* Unit test retrieval: given a query, it returns chunks from expected doc.
* Unit test citation formatting.
* Contract test: `/chat` returns stream + final payload format.

### Frontend tests

* Basic component rendering test (chat message list, citation drawer).
* Mock API streaming test.

### Tooling

* Pre-commit hooks (format/lint)
* Makefile or `justfile` for common commands

---

## 10) UX spec (quick wireframe in words)

### Main screen

* **Left sidebar:** profile card + quick prompt buttons + links
* **Center:** chat
* **Right drawer (optional):** “Sources” viewer for selected message

### Suggested prompts (ship with these)

* “Summarize the Mistral internship requirements and map them to Thomas’s experience.”
* “Give 3 STAR stories that best match the role.”
* “What are Thomas’s weaknesses for this role and mitigations?”
* “If you were the hiring manager, what follow-up questions would you ask?”

---

## 11) Milestones (tight, internship-project sized)

### Milestone A (MVP — 1 evening)

* Next.js chat UI (non-streaming)
* FastAPI `/chat` (no RAG, just Mistral call)
* README: setup + env vars

### Milestone B (RAG v1 — 1–2 evenings)

* Ingestion script + vector store
* Retrieval + citations shown in UI
* “I don’t know” behavior when not grounded

### Milestone C (Polish + eval — 1 evening)

* Streaming
* Sidebar profile + prompt chips
* Eval page (10 questions)

### Milestone D (Best practices)

* Docker compose
* Tests + CI workflow
* Short architecture diagram in README

---

## 12) README checklist (what reviewers care about)

* What it is + why it matches the internship prompt
* 1-minute demo GIF
* Setup:

  * `MISTRAL_API_KEY` env var
  * `docker-compose up` (or `pnpm dev` + `uvicorn`)
* How RAG works (short explanation)
* How to run tests
* Design tradeoffs (why FastAPI vs Next API routes; why this vector store)
* Future improvements

---

## 13) Content you should prepare (so the agent is “you”)

Create `data/thomas_profile.md` with:

* 5–8 “proof points” (projects with links, metrics if any)
* 3 STAR stories
* 1 paragraph: “Why Mistral”
* Skills matrix aligned to the posting bullets:

  * full-stack (Python/TS/JS) and/or infra
  * UX quality
  * building AI solutions with chat/embeddings 

---

## 14) Optional “wow” add-ons (only if time)

* “Explain my architecture” button that outputs a system design answer.
* A “groundedness” score: % of sentences with at least one citation.
* Support multiple models (dropdown) from Mistral’s platform.
