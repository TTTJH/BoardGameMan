"""
Routes for chat and Q&A functionality
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from typing import List
import logging
import json
import re
import time

from app.models import ChatMessage, ChatResponse, ChatHistoryResponse
from app.database import get_db_connection
from app.services.ai_service import AIService
from app.services.glossary_service import GlossaryService
from app.services.pdf_visual_assets import PDFVisualAssets
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter()
vector_store = VectorStore()


def now_ms() -> float:
    return time.perf_counter() * 1000


def elapsed_ms(start: float) -> int:
    return round(now_ms() - start)


VISUAL_TERM_ALIASES = {
    "地图板块": ["Map", "Tile deck", "Countryside tiles", "Core tiles"],
    "地图版块": ["Map", "Tile deck", "Countryside tiles", "Core tiles"],
    "地形板块": ["Map", "Tile deck", "Countryside tiles", "Core tiles"],
    "版图板块": ["Map", "Tile deck", "Countryside tiles", "Core tiles"],
    "板块": ["Tile deck", "Countryside tiles", "Core tiles"],
    "版块": ["Tile deck", "Countryside tiles", "Core tiles"],
    "地图": ["Map"],
    "源泉": ["Source"],
    "法力骰": ["Mana dice", "Source"],
    "法力骰子": ["Mana dice", "Source"],
    "骰子": ["Mana dice", "Source"],
    "伤口": ["Wound pile"],
    "法术": ["Spell deck", "Spell offer"],
    "高级行动": ["Advanced Action deck", "Advanced Action offer"],
    "单位": ["Unit offer", "Regular Unit deck", "Elite Unit deck"],
    "敌人": ["Enemy and Ruin token piles"],
    "废墟": ["Enemy and Ruin token piles"],
    "声望": ["Fame and Reputation board"],
    "名誉": ["Fame and Reputation board"],
    "战术": ["Tactics"],
}


COMMON_VISUAL_ALIASES = {
    "map tiles": ["地图板块", "地图", "地形板块"],
    "map": ["地图"],
    "fame and reputation board": ["名誉与声望版图", "名誉/声望版图", "名誉轨道", "声望轨道"],
    "fame track": ["名誉轨道", "名誉"],
    "reputation track": ["声望轨道", "声望"],
    "day/night board": ["昼夜版图", "日夜版图", "昼夜板", "日夜板"],
    "shield tokens": ["盾牌标记", "盾牌指示物", "盾牌"],
    "round order token": ["回合顺序指示物", "回合顺序标记"],
    "level tokens": ["等级标记", "等级指示物", "等级"],
    "skill tokens": ["技能标记", "技能指示物"],
    "hero card": ["英雄面板", "英雄卡"],
    "figure": ["英雄模型", "模型"],
    "player area": ["玩家区域", "玩家区"],
    "basic action cards": ["基础行动牌", "基础行动卡"],
    "advanced action cards": ["高级行动牌", "高级行动卡"],
    "spell cards": ["法术牌", "法术卡"],
    "artifact cards": ["神器牌", "神器卡"],
    "wound cards": ["伤口牌", "伤口牌堆"],
    "regular and elite unit cards": ["常规单位牌", "精英单位牌", "单位牌"],
    "tactic cards": ["战术卡", "战术牌"],
    "site description cards": ["地点描述卡", "地点说明卡"],
    "city cards": ["城市卡"],
    "mana dice": ["法力骰", "法力骰子"],
    "source": ["法力源泉", "源泉"],
}

GENERIC_ASSET_TERMS = {
    "component",
    "components",
    "icon",
    "icons",
    "token",
    "tokens",
    "tile",
    "tiles",
    "card",
    "cards",
    "board",
    "boards",
    "deck",
    "decks",
    "player",
    "players",
    "page",
    "source",
    "rule",
    "rules",
}

CHINESE_COMPONENT_SUFFIXES = (
    "板块",
    "版图",
    "卡牌",
    "牌库",
    "牌堆",
    "卡",
    "牌",
    "指示物",
    "标记物",
    "标记",
    "骰子",
    "骰",
    "模型",
    "面板",
    "区域",
    "供应区",
)


def build_source_response(game_id: int, source: str, query: str) -> dict:
    """Build a source object with readable text plus optional rendered PDF page."""
    excerpt = AIService.clean_source_excerpt(source, query)
    metadata = parse_source_metadata(source)
    page = parse_page_number(source)
    image_url = None
    filename = None
    source_type = None
    source_label = None

    document_id = metadata.get("document_id")
    if document_id and page:
        doc_info = document_info(game_id, document_id)
        if doc_info:
            filename = doc_info["filename"]
            source_type = doc_info["source_type"]
            source_label = source_type_label(source_type)
        ensure_visual_page_exists(game_id, document_id, page)
        image_url = PDFVisualAssets.page_url(game_id, document_id, page)

    return {
        "excerpt": excerpt,
        "page": page,
        "image_url": image_url,
        "highlight_regions": source_highlight_regions(game_id, metadata, page),
        "filename": filename,
        "document_id": document_id,
        "chunk_index": metadata.get("chunk_index"),
        "source_type": source_type,
        "source_label": source_label,
    }


def build_visual_references(
    game_id: int,
    sources: list[dict],
    response_text: str = "",
    limit: int = 12,
) -> list[dict]:
    """Build visual references from curated assets explicitly mentioned in the answer.

    Source page screenshots are still shown in the Sources area. Keeping this
    section curated-only prevents a cited page image from masquerading as a
    component reference.
    """
    return matching_game_assets(game_id, response_text, limit=limit)


def matching_game_assets(game_id: int, query_text: str, limit: int = 12) -> list[dict]:
    answer_text = query_text or ""
    normalized_query = normalize_match_text(answer_text)
    if not normalized_query:
        return []

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT a.*, d.filename, d.source_type
        FROM game_assets a
        LEFT JOIN documents d ON d.id = a.document_id
        WHERE a.game_id = ? AND a.enabled = 1
        ORDER BY a.updated_at DESC, a.id DESC
        """,
        (game_id,),
    ).fetchall()
    conn.close()

    matches = []
    for row in rows:
        terms = asset_match_terms(row)
        score = 0
        matched_terms = []
        for term in terms:
            matched = match_term_in_answer(answer_text, term)
            if not matched:
                continue
            matched_terms.append(matched)
            normalized_term = normalize_match_text(matched)
            score += max(6, len(normalized_term))
            if contains_cjk(matched):
                score += 4
        if score <= 0:
            continue

        title = row["display_name"] or row["name"]
        source_label = source_type_label(row["source_type"])
        subtitle_parts = [
            part for part in [
                row["asset_type"],
                row["filename"],
                f"Page {row['page']}" if row["page"] else None,
                source_label,
            ] if part
        ]
        matches.append((
            score,
            {
                "title": title,
                "subtitle": " - ".join(subtitle_parts),
                "image_url": row["image_path"],
                "matched_terms": list(dict.fromkeys(matched_terms))[:8],
                "page": row["page"],
                "filename": row["filename"],
                "document_id": row["document_id"],
                "source_type": row["source_type"],
                "source_label": source_label,
            },
        ))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [item for _score, item in matches[:limit]]


def asset_match_terms(row) -> list[str]:
    terms = []
    terms.extend(split_asset_terms(row["name"]))
    terms.extend(split_asset_terms(row["display_name"]))
    raw_keywords = row["keywords"]
    if raw_keywords:
        try:
            parsed = json.loads(raw_keywords)
            if isinstance(parsed, list):
                for item in parsed:
                    terms.extend(split_asset_terms(str(item)))
            else:
                terms.extend(split_asset_terms(str(parsed)))
        except json.JSONDecodeError:
            terms.extend(split_asset_terms(raw_keywords))
    expanded_terms = []
    for term in terms:
        expanded_terms.extend(expand_asset_term_aliases(term))
    return list(dict.fromkeys(
        term.strip()
        for term in expanded_terms
        if is_useful_asset_term(term)
    ))


def split_asset_terms(value: str | None) -> list[str]:
    if not value:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[,，;；\n]+", text)
    if len(parts) <= 1:
        parts = [text]
    return [part.strip() for part in parts if part.strip()]


def expand_asset_term_aliases(term: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (term or "").strip())
    if not cleaned:
        return []

    aliases = [cleaned]
    normalized = normalize_match_text(cleaned)
    aliases.extend(COMMON_VISUAL_ALIASES.get(normalized, []))

    if contains_cjk(cleaned):
        compact = re.sub(r"\s+", "", cleaned)
        aliases.append(compact)
        for suffix in CHINESE_COMPONENT_SUFFIXES:
            if compact.endswith(suffix) and len(compact) > len(suffix) + 1:
                aliases.append(compact[:-len(suffix)])
        for part in re.split(r"[、/／和与及]+", compact):
            if len(part) >= 2:
                aliases.append(part)
    else:
        aliases.extend(expand_english_visual_aliases(cleaned))

    return aliases


def expand_english_visual_aliases(term: str) -> list[str]:
    lower = normalize_match_text(term)
    aliases = []
    if lower.endswith("s") and len(lower) > 4:
        aliases.append(lower[:-1])
    else:
        aliases.append(f"{lower}s")

    slash_day_night = lower.replace("day night", "day/night")
    aliases.extend(COMMON_VISUAL_ALIASES.get(slash_day_night, []))
    return aliases


def is_useful_asset_term(term: str | None) -> bool:
    if not term:
        return False
    value = re.sub(r"\s+", " ", str(term)).strip(" .:：;；,，")
    if not value:
        return False
    normalized = normalize_match_text(value)
    if normalized in GENERIC_ASSET_TERMS:
        return False
    if contains_cjk(value):
        return len(value) >= 2
    if len(value) < 3 or len(value) > 72:
        return False
    if len(value.split()) > 8:
        return False
    if re.search(r"[.!?。！？]{1}", value):
        return False
    return True


def match_term_in_answer(answer_text: str, term: str) -> str | None:
    if not answer_text or not term:
        return None
    term = term.strip()
    if contains_cjk(term):
        return term if term in answer_text else None

    escaped = re.escape(term)
    escaped = re.sub(r"\\\s+", r"\\s+", escaped)
    pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    match = re.search(pattern, answer_text, re.IGNORECASE)
    return match.group(0) if match else None


def contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def normalize_match_text(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[\[\]【】()（）:：,，.。;；、/|_\\-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def has_legacy_auto_crops(visual_refs: list | None) -> bool:
    if not visual_refs:
        return False
    return any(
        isinstance(item, dict)
        and str(item.get("image_url", "")).startswith("/visual-refs/")
        for item in visual_refs
    )


def lacks_visual_match_terms(visual_refs: list | None) -> bool:
    if not visual_refs:
        return True
    return any(
        isinstance(item, dict)
        and item.get("image_url")
        and not item.get("matched_terms")
        for item in visual_refs
    )


def extract_visual_terms(response_text: str, limit: int = 16) -> list[str]:
    """Extract likely component names from an answer for visual lookup."""
    if not response_text:
        return []

    candidates = []
    alias_terms = []

    for trigger, terms in VISUAL_TERM_ALIASES.items():
        if trigger in response_text:
            alias_terms.extend(terms)

    for value in re.findall(r"\*\*([^*\n]{3,90})\*\*", response_text):
        candidates.append(value)

    for line in response_text.splitlines():
        match = re.match(r"\s*[-*]?\s*([A-Z][A-Za-z0-9/&' -]{2,70})\s*[（(:：]", line)
        if match:
            candidates.append(match.group(1))

    for value in re.findall(r"\b([A-Z][A-Za-z]+(?:\s+(?:and|of|the|[A-Z][A-Za-z]+|[A-Z]{2,})){1,6})\b", response_text):
        candidates.append(value)

    cleaned = []
    stop_terms = {
        "document",
        "source",
        "rulebook",
        "rules",
        "setup",
        "important",
        "note",
        "example",
    }
    for candidate in candidates:
        candidate = re.split(r"[（(]", candidate, maxsplit=1)[0]
        candidate = re.sub(r"\[[^\]]+\]", "", candidate)
        candidate = re.sub(r"^[0-9.、\s-]+", "", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip(" :：-")
        if len(candidate) < 4 or len(candidate) > 70:
            continue
        if not re.search(r"[A-Za-z]", candidate):
            continue
        if candidate.lower() in stop_terms:
            continue
        cleaned.append(candidate)

    return list(dict.fromkeys(alias_terms + cleaned))[:limit]


def parse_source_metadata(source: str) -> dict:
    match = re.search(r"^\[SourceMeta:\s*([^\]]+)\]", source or "")
    if not match:
        return {}
    metadata = {}
    for key, value in re.findall(r"(\w+)=([^\s\]]+)", match.group(1)):
        if key in {"document_id", "chunk_index"}:
            try:
                metadata[key] = int(value)
            except ValueError:
                pass
        else:
            metadata[key] = value
    return metadata


def parse_page_number(source: str) -> int | None:
    match = re.search(r"\[Page\s+(\d+)\]", source or "", re.IGNORECASE)
    return int(match.group(1)) if match else None


def ensure_visual_page_exists(game_id: int, document_id: int, page: int) -> None:
    page_path = PDFVisualAssets.page_path(game_id, document_id, page)
    if page_path.exists():
        return

    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT file_path FROM documents WHERE id = ? AND game_id = ?",
            (document_id, game_id),
        ).fetchone()
        conn.close()
        if row:
            PDFVisualAssets.render_pages(game_id, document_id, row["file_path"])
    except Exception as error:
        logger.warning(f"Could not ensure visual page for document {document_id} page {page}: {error}")


def document_info(game_id: int, document_id: int) -> dict | None:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT filename, source_type, file_path FROM documents WHERE id = ? AND game_id = ?",
        (document_id, game_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "filename": row["filename"],
        "source_type": row["source_type"] if "source_type" in row.keys() and row["source_type"] else "official_rulebook",
        "file_path": row["file_path"] if "file_path" in row.keys() else None,
    }


def load_json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def source_highlight_regions(game_id: int, metadata: dict, page: int | None) -> list[dict] | None:
    document_id = metadata.get("document_id")
    chunk_index = metadata.get("chunk_index")
    if not document_id or chunk_index is None or not page:
        return None

    conn = get_db_connection()
    try:
        chunk = conn.execute(
            """
            SELECT c.section_title, c.source_kind, c.metadata_json
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.document_id = ? AND c.chunk_index = ? AND d.game_id = ?
            """,
            (document_id, chunk_index, game_id),
        ).fetchone()
        if not chunk:
            return None

        metadata_json = load_json_dict(chunk["metadata_json"] if "metadata_json" in chunk.keys() else None)
        region_id = metadata_json.get("layout_region_id") or metadata_json.get("region_id")
        if region_id:
            regions = conn.execute(
                """
                SELECT bbox
                FROM document_layout_regions
                WHERE id = ? AND document_id = ? AND page = ? AND enabled = 1
                """,
                (region_id, document_id, page),
            ).fetchall()
        else:
            source_kind = chunk["source_kind"] if "source_kind" in chunk.keys() and chunk["source_kind"] else ""
            if source_kind != "layout_region":
                return None
            section_title = (chunk["section_title"] if "section_title" in chunk.keys() else "") or metadata_json.get("section") or ""
            if not section_title:
                return None
            regions = conn.execute(
                """
                SELECT bbox
                FROM document_layout_regions
                WHERE document_id = ? AND page = ? AND enabled = 1
                  AND COALESCE(region_type, 'rule') != 'ignore'
                  AND label = ?
                ORDER BY reading_order, id
                """,
                (document_id, page, section_title),
            ).fetchall()
        parsed_regions = []
        for region in regions:
            bbox = load_json_dict(region["bbox"])
            if valid_normalized_bbox(bbox):
                parsed_regions.append(bbox)
        return parsed_regions or None
    finally:
        conn.close()


def valid_normalized_bbox(bbox: dict) -> bool:
    try:
        x = float(bbox.get("x"))
        y = float(bbox.get("y"))
        width = float(bbox.get("width"))
        height = float(bbox.get("height"))
    except (TypeError, ValueError):
        return False
    return 0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1


def source_type_label(source_type: str | None) -> str:
    labels = {
        "official_rulebook": "Official Rulebook",
        "official_walkthrough": "Official Walkthrough",
        "official_faq": "Official FAQ",
        "official_errata": "Official Errata",
        "official_tutorial": "Official Tutorial",
        "community_qa": "Community Q&A",
        "player_guide": "Player Guide",
        "house_rule": "House Rule",
    }
    return labels.get(source_type or "", "Rulebook Source")


@router.post("/{game_id}/ask", response_model=ChatResponse)
async def ask_question(game_id: int, chat: ChatMessage):
    """Ask a question about the board game rules"""
    return await run_in_threadpool(process_question_sync, game_id, chat)


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{game_id}/ask-stream")
async def ask_question_stream(game_id: int, chat: ChatMessage):
    """Ask a question and stream the assistant text before final sources are ready."""
    return StreamingResponse(
        process_question_stream_sync(game_id, chat),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def process_question_stream_sync(game_id: int, chat: ChatMessage):
    total_started = now_ms()
    metrics = {
        "total_ms": 0,
        "game_lookup_ms": 0,
        "glossary_ms": 0,
        "retrieval_ms": 0,
        "llm_ms": 0,
        "source_build_ms": 0,
        "visual_refs_ms": 0,
        "db_ms": 0,
        "search": {},
        "llm": {},
        "response_length": 0,
        "source_count": 0,
        "visual_ref_count": 0,
        "streaming": True,
        "answer_mode": chat.answer_mode,
        "score": "unknown",
    }
    conn = None
    try:
        stage = now_ms()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM games WHERE id = ?", (game_id,))
        game_row = cursor.fetchone()
        if not game_row:
            yield sse_event("error", {"detail": "Game not found"})
            return

        game_name = game_row["name"]
        metrics["game_lookup_ms"] = elapsed_ms(stage)
        retrieval_message = (chat.retrieval_message or chat.display_message or chat.message).strip()

        stage = now_ms()
        glossary_rewrite = GlossaryService.rewrite_query(game_id, retrieval_message)
        search_query = glossary_rewrite["query"]
        metrics["retrieval_message"] = retrieval_message
        metrics["search_query"] = search_query
        metrics["glossary_ms"] = elapsed_ms(stage)

        stage = now_ms()
        request_vector_store = VectorStore()
        search_results = request_vector_store.search(game_id, search_query, top_k=8)
        metrics["retrieval_ms"] = elapsed_ms(stage)
        metrics["search"] = getattr(request_vector_store, "last_timing", {})
        yield sse_event("status", {"stage": "retrieved", "elapsed_ms": elapsed_ms(total_started)})

        if not search_results:
            response_text = f"I don't have any rulebook information for {game_name} yet. Please upload the rulebook PDF first."
            source_docs = []
            metrics["llm"] = {"skipped": True}
            yield sse_event("delta", {"text": response_text})
        else:
            documents = [doc for doc, score in search_results]
            ai_service = AIService()
            chunks = []
            stage = now_ms()
            stream = ai_service.stream_response(
                user_query=chat.message,
                context_documents=documents,
                game_name=game_name,
                answer_mode=chat.answer_mode,
            )
            try:
                while True:
                    text = next(stream)
                    chunks.append(text)
                    yield sse_event("delta", {"text": text})
            except StopIteration as done:
                response_text, source_indices = done.value
            metrics["llm_ms"] = elapsed_ms(stage)
            metrics["llm"] = getattr(ai_service, "last_timing", {})
            if not response_text:
                response_text = "".join(chunks)

            stage = now_ms()
            source_docs = [
                build_source_response(game_id, documents[i], retrieval_message)
                for i in source_indices
                if isinstance(i, int) and 0 <= i < len(documents)
            ]
            metrics["source_build_ms"] = elapsed_ms(stage)

        stage = now_ms()
        visual_refs = build_visual_references(game_id, source_docs, response_text)
        metrics["visual_refs_ms"] = elapsed_ms(stage)
        metrics["response_length"] = len(response_text or "")
        metrics["source_count"] = len(source_docs or [])
        metrics["visual_ref_count"] = len(visual_refs or [])

        stage = now_ms()
        sources_json = json.dumps(source_docs) if source_docs else None
        visual_refs_json = json.dumps(visual_refs) if visual_refs else None
        metrics["total_ms"] = elapsed_ms(total_started)
        metrics["score"] = response_latency_score(metrics["total_ms"])
        metrics_json = json.dumps(metrics, ensure_ascii=False)
        stored_user_message = (chat.display_message or chat.message).strip()
        cursor.execute(
            """INSERT INTO chat_history (
                game_id, user_message, assistant_response, sources, visual_refs, performance_metrics
            )
               VALUES (?, ?, ?, ?, ?, ?)""",
            (game_id, stored_user_message, response_text, sources_json, visual_refs_json, metrics_json)
        )
        conn.commit()
        chat_id = cursor.lastrowid
        metrics["db_ms"] = elapsed_ms(stage)
        metrics["total_ms"] = elapsed_ms(total_started)
        metrics["score"] = response_latency_score(metrics["total_ms"])
        metrics_json = json.dumps(metrics, ensure_ascii=False)
        cursor.execute(
            "UPDATE chat_history SET performance_metrics = ? WHERE id = ?",
            (metrics_json, chat_id),
        )
        conn.commit()

        yield sse_event("final", {
            "id": chat_id,
            "user_message": stored_user_message,
            "assistant_response": response_text,
            "sources": source_docs if source_docs else None,
            "visual_refs": visual_refs if visual_refs else None,
            "performance_metrics": metrics,
            "detailed_response": None,
            "detailed_sources": None,
            "detailed_visual_refs": None,
            "detailed_performance_metrics": None,
            "created_at": None,
        })
        logger.info(
            "CHAT_PERF_STREAM game=%s chat=%s total_ms=%s score=%s retrieval_ms=%s llm_ms=%s details=%s",
            game_id,
            chat_id,
            metrics["total_ms"],
            metrics["score"],
            metrics["retrieval_ms"],
            metrics["llm_ms"],
            json.dumps(metrics, ensure_ascii=False),
        )
    except Exception as e:
        logger.error(f"Error streaming chat: {e}")
        yield sse_event("error", {"detail": f"Error processing question: {str(e)}"})
    finally:
        if conn:
            conn.close()


def process_question_sync(game_id: int, chat: ChatMessage) -> ChatResponse:
    """Process one chat request in a worker thread because model clients are synchronous."""
    total_started = now_ms()
    metrics = {
        "total_ms": 0,
        "game_lookup_ms": 0,
        "glossary_ms": 0,
        "retrieval_ms": 0,
        "llm_ms": 0,
        "source_build_ms": 0,
        "visual_refs_ms": 0,
        "db_ms": 0,
        "search": {},
        "llm": {},
        "response_length": 0,
        "source_count": 0,
        "visual_ref_count": 0,
        "answer_mode": chat.answer_mode,
        "score": "unknown",
    }
    try:
        # Verify game exists
        stage = now_ms()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM games WHERE id = ?", (game_id,))
        game_row = cursor.fetchone()
        
        if not game_row:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        game_name = game_row['name']
        metrics["game_lookup_ms"] = elapsed_ms(stage)
        retrieval_message = (chat.retrieval_message or chat.display_message or chat.message).strip()
        
        # Search for relevant documents, expanding user phrasing with the game's glossary.
        stage = now_ms()
        glossary_rewrite = GlossaryService.rewrite_query(game_id, retrieval_message)
        search_query = glossary_rewrite["query"]
        metrics["retrieval_message"] = retrieval_message
        metrics["search_query"] = search_query
        metrics["glossary_ms"] = elapsed_ms(stage)

        stage = now_ms()
        request_vector_store = VectorStore()
        search_results = request_vector_store.search(game_id, search_query, top_k=8)
        metrics["retrieval_ms"] = elapsed_ms(stage)
        metrics["search"] = getattr(request_vector_store, "last_timing", {})
        
        if not search_results:
            # No documents found, return a helpful message
            response_text = f"I don't have any rulebook information for {game_name} yet. Please upload the rulebook PDF first."
            source_docs = []
            metrics["llm"] = {"skipped": True}
        else:
            # Extract documents and scores
            documents = [doc for doc, score in search_results]
            
            # Generate AI response
            ai_service = AIService()
            stage = now_ms()
            response_text, source_indices = ai_service.generate_response(
                user_query=chat.message,
                context_documents=documents,
                game_name=game_name,
                answer_mode=chat.answer_mode,
            )
            metrics["llm_ms"] = elapsed_ms(stage)
            metrics["llm"] = getattr(ai_service, "last_timing", {})
            
            # Get source documents - only include valid indices
            stage = now_ms()
            source_docs = [
                build_source_response(game_id, documents[i], retrieval_message)
                for i in source_indices 
                if isinstance(i, int) and 0 <= i < len(documents)
            ]
            metrics["source_build_ms"] = elapsed_ms(stage)
        stage = now_ms()
        visual_refs = build_visual_references(game_id, source_docs, response_text)
        metrics["visual_refs_ms"] = elapsed_ms(stage)
        metrics["response_length"] = len(response_text or "")
        metrics["source_count"] = len(source_docs or [])
        metrics["visual_ref_count"] = len(visual_refs or [])
        
        # Store chat in database
        stage = now_ms()
        sources_json = json.dumps(source_docs) if source_docs else None
        visual_refs_json = json.dumps(visual_refs) if visual_refs else None
        metrics["total_ms"] = elapsed_ms(total_started)
        metrics["score"] = response_latency_score(metrics["total_ms"])
        metrics_json = json.dumps(metrics, ensure_ascii=False)
        stored_user_message = (chat.display_message or chat.message).strip()
        cursor.execute(
            """INSERT INTO chat_history (
                game_id, user_message, assistant_response, sources, visual_refs, performance_metrics
            )
               VALUES (?, ?, ?, ?, ?, ?)""",
            (game_id, stored_user_message, response_text, sources_json, visual_refs_json, metrics_json)
        )
        conn.commit()
        chat_id = cursor.lastrowid
        
        # Fetch and return chat
        cursor.execute("SELECT * FROM chat_history WHERE id = ?", (chat_id,))
        row = cursor.fetchone()
        metrics["db_ms"] = elapsed_ms(stage)
        metrics["total_ms"] = elapsed_ms(total_started)
        metrics["score"] = response_latency_score(metrics["total_ms"])
        metrics_json = json.dumps(metrics, ensure_ascii=False)
        cursor.execute(
            "UPDATE chat_history SET performance_metrics = ? WHERE id = ?",
            (metrics_json, chat_id),
        )
        conn.commit()
        conn.close()
        
        logger.info(
            "CHAT_PERF game=%s chat=%s total_ms=%s score=%s retrieval_ms=%s llm_ms=%s visual_refs_ms=%s details=%s",
            game_id,
            chat_id,
            metrics["total_ms"],
            metrics["score"],
            metrics["retrieval_ms"],
            metrics["llm_ms"],
            metrics["visual_refs_ms"],
            json.dumps(metrics, ensure_ascii=False),
        )
        
        return ChatResponse(
            id=row['id'],
            user_message=row['user_message'],
            assistant_response=row['assistant_response'],
            sources=source_docs if source_docs else None,
            visual_refs=visual_refs if visual_refs else None,
            performance_metrics=metrics,
            detailed_response=None,
            detailed_sources=None,
            detailed_visual_refs=None,
            detailed_performance_metrics=None,
            created_at=row['created_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing question: {str(e)}"
        )


@router.post("/messages/{chat_id}/expand", response_model=ChatResponse)
async def expand_chat_message(chat_id: int):
    """Generate and persist a detailed explanation for an existing concise answer."""
    return await run_in_threadpool(process_expand_sync, chat_id)


def process_expand_sync(chat_id: int) -> ChatResponse:
    total_started = now_ms()
    metrics = {
        "total_ms": 0,
        "game_lookup_ms": 0,
        "glossary_ms": 0,
        "retrieval_ms": 0,
        "llm_ms": 0,
        "source_build_ms": 0,
        "visual_refs_ms": 0,
        "db_ms": 0,
        "search": {},
        "llm": {},
        "response_length": 0,
        "source_count": 0,
        "visual_ref_count": 0,
        "answer_mode": "detailed",
        "score": "unknown",
    }
    try:
        stage = now_ms()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT chat_history.*, games.name AS game_name
               FROM chat_history
               JOIN games ON games.id = chat_history.game_id
               WHERE chat_history.id = ?""",
            (chat_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat message not found")

        metrics["game_lookup_ms"] = elapsed_ms(stage)
        if "detailed_response" in row.keys() and row["detailed_response"]:
            response = chat_response_from_row(row)
            conn.close()
            return response

        game_id = row["game_id"]
        user_query = row["user_message"]
        game_name = row["game_name"]

        stage = now_ms()
        glossary_rewrite = GlossaryService.rewrite_query(game_id, user_query)
        search_query = glossary_rewrite["query"]
        metrics["glossary_ms"] = elapsed_ms(stage)

        stage = now_ms()
        request_vector_store = VectorStore()
        search_results = request_vector_store.search(game_id, search_query, top_k=8)
        metrics["retrieval_ms"] = elapsed_ms(stage)
        metrics["search"] = getattr(request_vector_store, "last_timing", {})

        if not search_results:
            detailed_response = f"I don't have enough rulebook information for {game_name} to expand this answer."
            detailed_sources = []
            metrics["llm"] = {"skipped": True}
        else:
            documents = [doc for doc, score in search_results]
            ai_service = AIService()
            stage = now_ms()
            detailed_response, source_indices = ai_service.generate_response(
                user_query=(
                    f"{user_query}\n\n"
                    "Give a more detailed explanation than the previous concise answer. "
                    "Clarify the rule sequence, edge cases, and examples only when supported by the excerpts."
                ),
                context_documents=documents,
                game_name=game_name,
                answer_mode="detailed",
            )
            metrics["llm_ms"] = elapsed_ms(stage)
            metrics["llm"] = getattr(ai_service, "last_timing", {})

            stage = now_ms()
            detailed_sources = [
                build_source_response(game_id, documents[i], user_query)
                for i in source_indices
                if isinstance(i, int) and 0 <= i < len(documents)
            ]
            metrics["source_build_ms"] = elapsed_ms(stage)

        stage = now_ms()
        detailed_visual_refs = build_visual_references(game_id, detailed_sources, detailed_response)
        metrics["visual_refs_ms"] = elapsed_ms(stage)
        metrics["response_length"] = len(detailed_response or "")
        metrics["source_count"] = len(detailed_sources or [])
        metrics["visual_ref_count"] = len(detailed_visual_refs or [])
        metrics["total_ms"] = elapsed_ms(total_started)
        metrics["score"] = response_latency_score(metrics["total_ms"])

        stage = now_ms()
        cursor.execute(
            """UPDATE chat_history
               SET detailed_response = ?,
                   detailed_sources = ?,
                   detailed_visual_refs = ?,
                   detailed_performance_metrics = ?
               WHERE id = ?""",
            (
                detailed_response,
                json.dumps(detailed_sources, ensure_ascii=False) if detailed_sources else None,
                json.dumps(detailed_visual_refs, ensure_ascii=False) if detailed_visual_refs else None,
                json.dumps(metrics, ensure_ascii=False),
                chat_id,
            ),
        )
        conn.commit()
        metrics["db_ms"] = elapsed_ms(stage)
        metrics["total_ms"] = elapsed_ms(total_started)
        metrics["score"] = response_latency_score(metrics["total_ms"])
        cursor.execute(
            "UPDATE chat_history SET detailed_performance_metrics = ? WHERE id = ?",
            (json.dumps(metrics, ensure_ascii=False), chat_id),
        )
        conn.commit()

        cursor.execute("SELECT * FROM chat_history WHERE id = ?", (chat_id,))
        updated = cursor.fetchone()
        conn.close()
        logger.info(
            "CHAT_EXPAND_PERF chat=%s total_ms=%s score=%s retrieval_ms=%s llm_ms=%s details=%s",
            chat_id,
            metrics["total_ms"],
            metrics["score"],
            metrics["retrieval_ms"],
            metrics["llm_ms"],
            json.dumps(metrics, ensure_ascii=False),
        )
        return chat_response_from_row(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error expanding chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error expanding answer: {str(e)}",
        )


def parse_json_column(row, column: str):
    if column not in row.keys() or not row[column]:
        return None
    return json.loads(row[column])


def chat_response_from_row(row) -> ChatResponse:
    return ChatResponse(
        id=row["id"],
        user_message=row["user_message"],
        assistant_response=row["assistant_response"],
        sources=parse_json_column(row, "sources"),
        visual_refs=parse_json_column(row, "visual_refs"),
        performance_metrics=parse_json_column(row, "performance_metrics"),
        detailed_response=row["detailed_response"] if "detailed_response" in row.keys() else None,
        detailed_sources=parse_json_column(row, "detailed_sources"),
        detailed_visual_refs=parse_json_column(row, "detailed_visual_refs"),
        detailed_performance_metrics=parse_json_column(row, "detailed_performance_metrics"),
        created_at=row["created_at"],
    )


def response_latency_score(total_ms: int) -> str:
    if total_ms < 8000:
        return "excellent"
    if total_ms < 15000:
        return "acceptable"
    if total_ms < 25000:
        return "slow"
    return "poor"


@router.get("/{game_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(game_id: int, limit: int = 50, offset: int = 0):
    """Get chat history for a game"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify game exists
        cursor.execute("SELECT id FROM games WHERE id = ?", (game_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        # Get total count
        cursor.execute("SELECT COUNT(*) as count FROM chat_history WHERE game_id = ?", (game_id,))
        total = cursor.fetchone()['count']
        
        # Get paginated results
        cursor.execute(
            """SELECT * FROM chat_history WHERE game_id = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (game_id, limit, offset)
        )
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            sources = parse_json_column(row, "sources")
            visual_refs = parse_json_column(row, "visual_refs")
            performance_metrics = parse_json_column(row, "performance_metrics")
            detailed_visual_refs = parse_json_column(row, "detailed_visual_refs")
            if (
                (not visual_refs or has_legacy_auto_crops(visual_refs) or lacks_visual_match_terms(visual_refs))
                and sources
                and all(isinstance(source, dict) for source in sources)
            ):
                visual_refs = build_visual_references(game_id, sources, row['assistant_response'])
            detailed_sources = parse_json_column(row, "detailed_sources")
            if (
                row["detailed_response"] if "detailed_response" in row.keys() else None
            ) and (
                not detailed_visual_refs
                or has_legacy_auto_crops(detailed_visual_refs)
                or lacks_visual_match_terms(detailed_visual_refs)
            ) and detailed_sources and all(isinstance(source, dict) for source in detailed_sources):
                detailed_visual_refs = build_visual_references(game_id, detailed_sources, row["detailed_response"])
            messages.append(ChatResponse(
                id=row['id'],
                user_message=row['user_message'],
                assistant_response=row['assistant_response'],
                sources=sources,
                visual_refs=visual_refs if visual_refs else None,
                performance_metrics=performance_metrics,
                detailed_response=row["detailed_response"] if "detailed_response" in row.keys() else None,
                detailed_sources=detailed_sources,
                detailed_visual_refs=detailed_visual_refs if detailed_visual_refs else None,
                detailed_performance_metrics=parse_json_column(row, "detailed_performance_metrics"),
                created_at=row['created_at']
            ))
        
        return ChatHistoryResponse(messages=messages, total=total)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat history"
        )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_message(chat_id: int):
    """Delete a chat message"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM chat_history WHERE id = ?", (chat_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat message not found"
            )
        
        cursor.execute("DELETE FROM chat_history WHERE id = ?", (chat_id,))
        conn.commit()
        conn.close()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting chat message"
        )
