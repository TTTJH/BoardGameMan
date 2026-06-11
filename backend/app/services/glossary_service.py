"""Rulebook glossary extraction, storage, and query rewriting."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from openai import OpenAI

from app.database import get_db_connection
from app.services.model_config import get_model_config

logger = logging.getLogger(__name__)


TERM_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][A-Za-z]+|[A-Z]{2,}|of|and|the|or|to)){0,4}\b"
)
PAGE_RE = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)
SECTION_RE = re.compile(r"\[Section:\s*([^\]]+)\]", re.IGNORECASE)
SOURCE_RE = re.compile(r"\[SourceMeta:\s*document_id=(\d+)\s+chunk_index=(\d+)\]", re.IGNORECASE)


STOP_TERMS = {
    "A",
    "An",
    "All",
    "Any",
    "As",
    "At",
    "Before",
    "By",
    "During",
    "Each",
    "Example",
    "For",
    "From",
    "If",
    "In",
    "It",
    "Note",
    "Other",
    "On",
    "Page",
    "Section",
    "See",
    "See the",
    "SourceMeta",
    "Document",
    "Rulebook",
    "Rulebook Context",
    "Game",
    "The Game",
    "The",
    "This",
    "These",
    "To",
    "When",
    "Whenever",
    "You",
    "A Player",
    "Player",
    "Players",
}

SINGLE_WORD_TERMS = {
    "Action",
    "Actions",
    "Armor",
    "Artifact",
    "Artifacts",
    "Attack",
    "Attacks",
    "Block",
    "Cards",
    "City",
    "Combat",
    "Crystals",
    "Damage",
    "Deed",
    "Enemy",
    "Enemies",
    "Fame",
    "Fire",
    "Hero",
    "Heroes",
    "Influence",
    "Mana",
    "Map",
    "Movement",
    "Reputation",
    "Round",
    "Scenario",
    "Shield",
    "Skill",
    "Skills",
    "Source",
    "Spell",
    "Spells",
    "Tactic",
    "Tactics",
    "Unit",
    "Units",
    "Wound",
    "Wounds",
}


class GlossaryService:
    """Manage game-specific terminology discovered during rulebook processing."""

    MAX_TERMS = 80

    @staticmethod
    def regenerate_for_game(game_id: int, limit: int = MAX_TERMS, use_llm: bool = False) -> List[Dict]:
        candidates = GlossaryService.extract_candidates(game_id, limit=limit)
        enriched = (
            GlossaryService._enrich_with_llm(candidates)
            if use_llm
            else [{key: value for key, value in item.items() if key != "contexts"} for item in candidates]
        )
        GlossaryService.replace_terms(game_id, enriched)
        return GlossaryService.list_terms(game_id, enabled_only=False)

    @staticmethod
    def extract_candidates(game_id: int, limit: int = MAX_TERMS) -> List[Dict]:
        conn = get_db_connection()
        rows = conn.execute(
            """
            SELECT c.chunk_index, c.content, c.rule_type
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.game_id = ? AND COALESCE(c.enabled, 1) = 1
            ORDER BY c.document_id, c.chunk_index
            """,
            (game_id,),
        ).fetchall()
        conn.close()

        stats: Dict[str, Dict] = {}
        contexts = defaultdict(list)
        for row in rows:
            content = row["content"]
            page = GlossaryService._page(content)
            chunk_index = row["chunk_index"]
            section = GlossaryService._section(content)

            for term in GlossaryService._candidate_terms(content, section):
                normalized = GlossaryService._normalize_term(term)
                if not GlossaryService._is_good_term(normalized):
                    continue

                item = stats.setdefault(normalized, {
                    "term": normalized,
                    "count": 0,
                    "pages": set(),
                    "chunks": set(),
                    "types": Counter(),
                })
                item["count"] += 1
                if page:
                    item["pages"].add(page)
                item["chunks"].add(chunk_index)
                item["types"].update([row["rule_type"] or "term"])
                if len(contexts[normalized]) < 2:
                    contexts[normalized].append(GlossaryService._context_excerpt(content, normalized))

        ranked = sorted(stats.values(), key=GlossaryService._candidate_sort_key, reverse=True)
        results = []
        for item in ranked[:limit]:
            term_type = item["types"].most_common(1)[0][0] if item["types"] else "term"
            results.append({
                "term": item["term"],
                "aliases": [],
                "term_type": term_type,
                "description": "",
                "source_pages": sorted(item["pages"]),
                "chunk_refs": sorted(item["chunks"]),
                "related_terms": [],
                "search_terms": [item["term"], item["term"].lower()],
                "enabled": True,
                "importance": float(item["count"] + len(item["pages"]) * 0.6),
                "contexts": contexts[item["term"]],
            })
        return results

    @staticmethod
    def replace_terms(game_id: int, terms: List[Dict]) -> None:
        conn = get_db_connection()
        conn.execute("DELETE FROM glossary_terms WHERE game_id = ?", (game_id,))
        for term in terms:
            conn.execute(
                """
                INSERT OR REPLACE INTO glossary_terms
                (game_id, term, aliases, term_type, description, source_pages, chunk_refs,
                 related_terms, search_terms, enabled, importance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game_id,
                    term["term"],
                    GlossaryService._json(term.get("aliases", [])),
                    term.get("term_type", "term"),
                    term.get("description") or "",
                    GlossaryService._json(term.get("source_pages", [])),
                    GlossaryService._json(term.get("chunk_refs", [])),
                    GlossaryService._json(term.get("related_terms", [])),
                    GlossaryService._json(term.get("search_terms", [term["term"]])),
                    1 if term.get("enabled", True) else 0,
                    term.get("importance", 0),
                ),
            )
        conn.commit()
        conn.close()

    @staticmethod
    def list_terms(game_id: int, enabled_only: bool = True, limit: Optional[int] = None) -> List[Dict]:
        conn = get_db_connection()
        sql = """
            SELECT *
            FROM glossary_terms
            WHERE game_id = ?
        """
        params = [game_id]
        if enabled_only:
            sql += " AND COALESCE(enabled, 1) = 1"
        sql += " ORDER BY importance DESC, term COLLATE NOCASE"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [GlossaryService._row_to_dict(row) for row in rows]

    @staticmethod
    def update_term(term_id: int, payload: Dict) -> Optional[Dict]:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM glossary_terms WHERE id = ?", (term_id,)).fetchone()
        if not row:
            conn.close()
            return None

        search_terms = payload.get("search_terms") or [payload["term"], *payload.get("aliases", [])]
        conn.execute(
            """
            UPDATE glossary_terms
            SET term = ?, aliases = ?, term_type = ?, description = ?,
                related_terms = ?, search_terms = ?, enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload["term"],
                GlossaryService._json(payload.get("aliases", [])),
                payload.get("term_type", "term"),
                payload.get("description") or "",
                GlossaryService._json(payload.get("related_terms", [])),
                GlossaryService._json(search_terms),
                1 if payload.get("enabled", True) else 0,
                term_id,
            ),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM glossary_terms WHERE id = ?", (term_id,)).fetchone()
        conn.close()
        return GlossaryService._row_to_dict(updated)

    @staticmethod
    def rewrite_query(game_id: int, query: str) -> Dict:
        terms = GlossaryService.list_terms(game_id, enabled_only=True, limit=120)
        matches = GlossaryService.match_terms(query, terms)
        if not matches:
            return {"query": query, "matches": []}

        expansions = []
        for match in matches[:3]:
            expansions.extend([match["term"], *match.get("aliases", []), *match.get("search_terms", [])])
            expansions.extend(match.get("related_terms", []))

        expansion_text = " ".join(GlossaryService._unique(part for part in expansions if part))
        return {
            "query": f"{query}\n\nGlossary expansion: {expansion_text}",
            "matches": matches[:3],
        }

    @staticmethod
    def match_terms(query: str, terms: List[Dict]) -> List[Dict]:
        normalized_query = GlossaryService._normalize_for_match(query)
        if not normalized_query:
            return []

        scored = []
        for term in terms:
            labels = [term["term"], *term.get("aliases", []), *term.get("search_terms", [])]
            best = 0.0
            for label in labels:
                normalized_label = GlossaryService._normalize_for_match(label)
                if not normalized_label:
                    continue
                if normalized_label in normalized_query:
                    best = max(best, 1.0)
                elif normalized_query in normalized_label and len(normalized_query) >= 3:
                    best = max(best, 0.86)
                else:
                    best = max(best, SequenceMatcher(None, normalized_query, normalized_label).ratio())

            if best >= 0.72:
                scored.append({**term, "score": round(best, 3)})

        return sorted(scored, key=lambda item: (item["score"], item["importance"]), reverse=True)

    @staticmethod
    def _enrich_with_llm(candidates: List[Dict]) -> List[Dict]:
        config = get_model_config()["chat"]
        if not config["api_key"] or not candidates:
            return [{key: value for key, value in item.items() if key != "contexts"} for item in candidates]

        payload = [
            {
                "term": item["term"],
                "type": item["term_type"],
                "pages": item["source_pages"][:6],
                "contexts": item["contexts"],
            }
            for item in candidates[:50]
        ]
        try:
            client = OpenAI(api_key=config["api_key"], base_url=config["api_base"])
            response = client.chat.completions.create(
                model=config["model"],
                temperature=0.1,
                max_tokens=3000,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You build board-game rulebook glossaries. Return JSON only. "
                            "For each input term, provide concise Chinese aliases users may type, "
                            "a short Chinese description, related English terms, and a type. "
                            "Do not invent rules; infer only terminology from context."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
            )
            raw = response.choices[0].message.content or "[]"
            parsed = GlossaryService._parse_json_array(raw)
            by_term = {item.get("term"): item for item in parsed if item.get("term")}
            enriched = []
            for item in candidates:
                extra = by_term.get(item["term"], {})
                aliases = GlossaryService._unique([*item.get("aliases", []), *extra.get("aliases", [])])
                related = GlossaryService._unique([*item.get("related_terms", []), *extra.get("related_terms", [])])
                search_terms = GlossaryService._unique([
                    *item.get("search_terms", []),
                    item["term"],
                    *aliases,
                    *related,
                    *extra.get("search_terms", []),
                ])
                enriched.append({
                    **{key: value for key, value in item.items() if key != "contexts"},
                    "aliases": aliases[:8],
                    "term_type": extra.get("term_type") or extra.get("type") or item.get("term_type", "term"),
                    "description": extra.get("description") or item.get("description", ""),
                    "related_terms": related[:8],
                    "search_terms": search_terms[:18],
                })
            return enriched
        except Exception as error:
            logger.warning(f"Could not enrich glossary with LLM: {error}")
            return [{key: value for key, value in item.items() if key != "contexts"} for item in candidates]

    @staticmethod
    def _candidate_terms(content: str, section: str = "") -> List[str]:
        cleaned = re.sub(r"\[[^\]]+\]", " ", content)
        candidates = []
        if section:
            candidates.append(section)

        candidates.extend(match.group(0) for match in TERM_RE.finditer(cleaned))
        quoted = re.findall(r'"([^"]{3,60})"|“([^”]{3,60})”', cleaned)
        for left, right in quoted:
            candidates.append(left or right)
        return candidates

    @staticmethod
    def _is_good_term(term: str) -> bool:
        if not term or term in STOP_TERMS:
            return False
        if len(term) < 3 or len(term) > 70:
            return False
        if any(marker in term for marker in ["\u00e2", "\u0080", "\ufffd", "~~~"]):
            return False
        if re.search(r"[^\w\s()/-]{2,}", term):
            return False
        if re.search(r"\b[A-Z]{3,}\s+Player\b", term):
            return False
        if re.fullmatch(r"\d+|Page\s+\d+|Document\s+\d+", term, re.IGNORECASE):
            return False
        words = term.split()
        if len(words) > 6:
            return False
        if len(words) == 1 and term not in SINGLE_WORD_TERMS:
            return False
        if words and words[0] in STOP_TERMS:
            return False
        alpha_count = sum(1 for ch in term if ch.isalpha())
        return alpha_count >= 3

    @staticmethod
    def _candidate_sort_key(item: Dict) -> tuple:
        phrase_bonus = 8 if len(item["term"].split()) >= 2 else 0
        page_bonus = min(len(item["pages"]), 6)
        broad_penalty = 8 if len(item["pages"]) > 12 and len(item["term"].split()) == 1 else 0
        return (item["count"] + phrase_bonus + page_bonus - broad_penalty, len(item["chunks"]))

    @staticmethod
    def _context_excerpt(content: str, term: str, radius: int = 180) -> str:
        plain = re.sub(r"\s+", " ", content)
        index = plain.lower().find(term.lower())
        if index < 0:
            return plain[: radius * 2]
        start = max(index - radius, 0)
        return plain[start:index + len(term) + radius]

    @staticmethod
    def _row_to_dict(row) -> Dict:
        return {
            "id": row["id"],
            "game_id": row["game_id"],
            "term": row["term"],
            "aliases": GlossaryService._loads(row["aliases"]),
            "term_type": row["term_type"] or "term",
            "description": row["description"],
            "source_pages": GlossaryService._loads(row["source_pages"]),
            "chunk_refs": GlossaryService._loads(row["chunk_refs"]),
            "related_terms": GlossaryService._loads(row["related_terms"]),
            "search_terms": GlossaryService._loads(row["search_terms"]),
            "enabled": bool(row["enabled"]),
            "importance": float(row["importance"] or 0),
        }

    @staticmethod
    def _page(content: str) -> Optional[int]:
        match = PAGE_RE.search(content or "")
        return int(match.group(1)) if match else None

    @staticmethod
    def _section(content: str) -> str:
        match = SECTION_RE.search(content or "")
        return GlossaryService._normalize_term(match.group(1)) if match else ""

    @staticmethod
    def _normalize_term(term: str) -> str:
        term = re.sub(r"\s+", " ", term or "").strip(" -:~.\t")
        term = re.sub(r"([()])\1{2,}", r"\1", term)
        return term

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"[\s_\-:：，。,.;；!?！？'\"“”‘’()（）]+", "", text)
        return text

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value or [], ensure_ascii=False)

    @staticmethod
    def _loads(value: str) -> List:
        if not value:
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    @staticmethod
    def _unique(values) -> List[str]:
        return [value for value in dict.fromkeys(str(v).strip() for v in values if str(v).strip())]

    @staticmethod
    def _parse_json_array(raw: str) -> List[Dict]:
        raw = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1).strip()
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else parsed.get("terms", [])
