# Rulebook Evaluation Tools

This folder contains offline tools for measuring and improving rulebook ingestion quality.

The first tool generates candidate retrieval-evaluation questions from already-ingested chunks.
Generated files are only candidates. Review them before promoting them into stable eval cases.

## Generate Candidate Questions

```powershell
cd D:\Code\boardGameMan\backend
.\.venv\Scripts\python.exe evals\generate_candidate_questions.py --game-id 21 --max-pages 8 --questions-per-page 3
```

Output goes to:

```text
backend/evals/candidates/game_<id>_candidate_questions.json
```

Each candidate includes:

- `question`
- `expected_pages`
- `expected_terms`
- `evidence_quote`
- `category`
- `review_notes`
- `status`

