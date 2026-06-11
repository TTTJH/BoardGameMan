"""Generate candidate retrieval-eval questions from ingested rulebook chunks.

The output is intentionally marked as candidate material. A human should review
and promote useful items into stable eval cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import get_db_connection, init_db
from app.services.ai_service import AIService
from app.services.model_config import get_model_config


DEFAULT_CATEGORIES = [
    "turn_structure",
    "action",
    "scoring",
    "timing",
    "cost",
    "exception",
    "setup",
    "end_game",
    "component",
    "variant",
]


def main() -> None:
    args = parse_args()
    payload, output_path = generate_candidate_questions(
        game_id=args.game_id,
        max_pages=args.max_pages,
        questions_per_page=args.questions_per_page,
        max_chars_per_page=args.max_chars_per_page,
        output_path=args.output,
    )

    print(f"Wrote {len(payload['candidates'])} candidates to {output_path}")


def generate_candidate_questions(
    game_id: int,
    max_pages: int = 8,
    questions_per_page: int = 3,
    max_chars_per_page: int = 4200,
    output_path: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    init_db()

    game = load_game(game_id)
    if not game:
        raise ValueError(f"Game {game_id} not found.")

    page_chunks = load_page_chunks(game_id)
    if not page_chunks:
        raise ValueError(f"Game {game_id} has no chunks to inspect.")

    selected_pages = select_pages(page_chunks, max_pages)
    client, model = build_client()

    all_candidates: list[dict[str, Any]] = []
    for page in selected_pages:
        excerpt = build_page_excerpt(page, page_chunks[page], max_chars_per_page)
        candidates = generate_for_page(
            client=client,
            model=model,
            game_name=game["name"],
            page=page,
            excerpt=excerpt,
            questions_per_page=questions_per_page,
        )
        all_candidates.extend(normalize_candidates(game_id, game["name"], page, candidates))

    resolved_output_path = output_path or (
        ROOT / "evals" / "candidates" / f"game_{game_id}_candidate_questions.json"
    )
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "game_id": game_id,
        "game_name": game["name"],
        "status": "candidate",
        "generator": {
            "model": model,
            "max_pages": max_pages,
            "questions_per_page": questions_per_page,
        },
        "candidates": all_candidates,
    }
    resolved_output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload, resolved_output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate candidate rulebook eval questions.")
    parser.add_argument("--game-id", type=int, required=True, help="Game id from the local database.")
    parser.add_argument("--max-pages", type=int, default=8, help="Maximum pages to sample.")
    parser.add_argument("--questions-per-page", type=int, default=3, help="Questions to generate per page.")
    parser.add_argument("--max-chars-per-page", type=int, default=4200, help="Maximum excerpt chars sent per page.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON path.")
    return parser.parse_args()


def load_game(game_id: int) -> dict[str, Any] | None:
    conn = get_db_connection()
    row = conn.execute("SELECT id, name FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def load_page_chunks(game_id: int) -> dict[int, list[str]]:
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT c.content
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.game_id = ?
        ORDER BY d.id, c.chunk_index
        """,
        (game_id,),
    ).fetchall()
    conn.close()

    pages: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        text = AIService.strip_source_metadata(row["content"])
        match = re.search(r"\[Page\s+(\d+)\]", text, re.IGNORECASE)
        if not match:
            continue
        pages[int(match.group(1))].append(AIService.clean_context_document(text))
    return dict(pages)


def select_pages(page_chunks: dict[int, list[str]], max_pages: int) -> list[int]:
    scored = []
    for page, chunks in page_chunks.items():
        text = "\n".join(chunks).lower()
        signal = 0
        signal += len(re.findall(r"\b(score|victory|points|action|turn|phase|may|must|when|if|end of the game)\b", text))
        signal += min(len(text) // 500, 8)
        scored.append((page, signal))
    return [
        page
        for page, _ in sorted(scored, key=lambda item: (-item[1], item[0]))[:max_pages]
    ]


def build_page_excerpt(page: int, chunks: list[str], max_chars: int) -> str:
    text = "\n\n".join(chunks)
    text = re.sub(r"\s+", " ", text).strip()
    return f"[Page {page}]\n{text[:max_chars]}"


def build_client() -> tuple[OpenAI, str]:
    config = get_model_config()["chat"]
    if not config["api_key"]:
        raise SystemExit("Chat API key is not configured. Set it in Model Settings or backend/.env.")
    return OpenAI(api_key=config["api_key"], base_url=config["api_base"]), config["model"]


def generate_for_page(
    client: OpenAI,
    model: str,
    game_name: str,
    page: int,
    excerpt: str,
    questions_per_page: int,
) -> list[dict[str, Any]]:
    prompt = f"""
You generate candidate retrieval-evaluation questions for a board-game rulebook assistant.

Game: {game_name}
Rulebook page: {page}

Create {questions_per_page} candidate questions that real players might ask based only on this excerpt.

Requirements:
- Questions should be in Chinese.
- Each question must be answerable from the excerpt.
- Prefer rules that are easy to misunderstand: timing, scoring, costs, exceptions, variants, setup, end game.
- Use exact English evidence terms from the excerpt for expected_terms.
- expected_terms should contain 2-5 short phrases that a retrieval system should find.
- evidence_quote should be a short exact quote from the excerpt.
- category must be one of: {", ".join(DEFAULT_CATEGORIES)}.
- Do not invent rules outside the excerpt.

Return only valid JSON with this shape:
[
  {{
    "question": "...",
    "expected_pages": [{page}],
    "expected_terms": ["...", "..."],
    "evidence_quote": "...",
    "category": "scoring",
    "review_notes": "..."
  }}
]

Excerpt:
{excerpt}
""".strip()

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=1600,
        messages=[
            {"role": "system", "content": "You return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "[]"
    return parse_json_array(content)


def parse_json_array(content: str) -> list[dict[str, Any]]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", content)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise ValueError("Model did not return a JSON array.")
    return [item for item in data if isinstance(item, dict)]


def normalize_candidates(
    game_id: int,
    game_name: str,
    page: int,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = []
    for candidate in candidates:
        question = str(candidate.get("question", "")).strip()
        if not question:
            continue

        expected_pages = candidate.get("expected_pages") or [page]
        expected_terms = candidate.get("expected_terms") or []
        if not isinstance(expected_pages, list):
            expected_pages = [page]
        if not isinstance(expected_terms, list):
            expected_terms = []

        case_id = stable_case_id(game_name, question)
        category = candidate.get("category", "action")
        if category not in DEFAULT_CATEGORIES:
            category = "action"

        normalized.append({
            "id": case_id,
            "game_id": game_id,
            "game_name": game_name,
            "question": question,
            "expected_pages": [int(value) for value in expected_pages if str(value).isdigit()] or [page],
            "expected_terms": [str(value).strip() for value in expected_terms if str(value).strip()],
            "evidence_quote": str(candidate.get("evidence_quote", "")).strip(),
            "category": category,
            "review_notes": str(candidate.get("review_notes", "")).strip(),
            "status": "candidate",
        })
    return normalized


def stable_case_id(game_name: str, question: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", game_name.lower()).strip("_")[:28] or "game"
    digest = hashlib.sha1(question.encode("utf-8")).hexdigest()[:10]
    return f"{slug}_{digest}"


if __name__ == "__main__":
    main()
