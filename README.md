# BoardGameMan

BoardGameMan is a local-first board game rulebook assistant. It lets an admin upload PDF rulebooks, process them into searchable rule units, review extraction quality, and ask rule questions through a chat UI with sources and visual references.

## Features

- PDF rulebook upload and processing
- Rulebook chunking with rule-unit metadata such as setup, action, scoring, variant, example, and component
- Retrieval-augmented chat over one or more uploaded documents for a game
- Source cards with document name, page number, page thumbnails, and highlighted evidence regions
- Manual PDF layout region marking for difficult multi-column or block-based pages
- Manual game asset library for tokens, boards, cards, icons, and components
- Hoverable visual references inside chat answers
- Evaluation tools for generated and promoted QA cases
- Configurable chat, embedding, and reranker models through the admin UI
- Internationalized frontend UI with English, Chinese, Japanese, and Korean labels

## Tech Stack

- Frontend: React, Vite, Tailwind CSS, Zustand
- Backend: FastAPI, SQLite, pdfplumber, PyPDF2, pypdfium2, Pillow
- Retrieval: local SQLite fallback and optional ChromaDB/vector embeddings
- Models: OpenAI-compatible chat, embedding, and rerank endpoints

## Repository Layout

```text
backend/        FastAPI backend, PDF processing, retrieval, evaluation, model config
frontend/       React/Vite frontend
.github/        Project instructions and GitHub-related files
setup.bat       Windows setup helper
setup.sh        Unix setup helper
```

Runtime data is intentionally ignored by Git. This includes uploaded PDFs, generated page images, game assets, SQLite databases, vector stores, logs, virtual environments, and frontend build output.

## Prerequisites

- Python 3.10 or 3.11 recommended
- Node.js 18+
- An OpenAI-compatible chat model API key
- Optional embedding/rerank API keys for higher retrieval quality

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set the model configuration you want to use:

```env
OPENAI_API_KEY=your_chat_model_key
OPENAI_API_BASE=https://api.openai.com/v1
MODEL_NAME=gpt-3.5-turbo

EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-8B

RERANK_ENABLED=false
RERANK_MODEL=Qwen/Qwen3-VL-Reranker-8B
RERANK_CANDIDATES=30
RERANK_TOP_N=8
```

Start the backend:

```powershell
python main.py
```

The API runs at:

```text
http://localhost:8000
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Frontend Setup

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at:

```text
http://localhost:3000
```

The Vite dev server proxies `/api`, `/covers`, `/rule-pages`, `/visual-refs`, and `/game-assets` to the backend.

## Typical Workflow

1. Open the admin kitchen.
2. Create a board game entry.
3. Upload one or more official rulebook, walkthrough, FAQ, or reference PDFs.
4. Reprocess the PDFs to build rule chunks, page previews, embeddings, and reports.
5. Use the quality report to inspect low-quality pages.
6. Mark special PDF layout regions when a page has columns, overlapping examples, or dense tables.
7. Add manual game assets for important tokens, cards, boards, icons, and components.
8. Ask questions in the game lounge and verify answers against visible sources.
9. Promote good eval cases and run retrieval/chat evals before large parser changes.

## Notes

- `backend/.env` is ignored and must not be committed.
- Uploaded PDFs and generated images are ignored because they are large runtime data and may contain copyrighted material.
- Local SQLite databases and vector stores are ignored because they can be rebuilt from uploaded documents.
- If ChromaDB is not available in the local environment, the project can still run with the SQLite retrieval fallback, though retrieval quality may be lower.
