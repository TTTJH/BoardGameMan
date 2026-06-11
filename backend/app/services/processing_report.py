"""Processing report generation for rulebook ingestion."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Dict, List, Optional

from app.database import get_db_connection
from app.services.pdf_processor import TextChunker


class ProcessingReport:
    """Build and persist measurable ingestion quality reports."""

    @staticmethod
    def build(
        *,
        page_count: int,
        cleaned_text: str,
        chunks: List[Dict],
        chunk_stats: Dict,
        embedding_attempted: bool,
        embedding_success: bool,
        embedding_error: Optional[str] = None,
    ) -> Dict:
        page_texts = ProcessingReport._page_texts(cleaned_text)
        empty_pages = [
            page
            for page in range(1, page_count + 1)
            if len(page_texts.get(str(page), "").strip()) < 20
        ]
        suspicious_pages = ProcessingReport._suspicious_pages(page_texts)
        rule_type_counts = Counter(
            chunk.get("metadata", {}).get("type", "text")
            for chunk in chunks
        )
        rule_scope_counts = Counter(
            chunk.get("metadata", {}).get("rule_scope", "base")
            for chunk in chunks
        )
        source_kind_counts = Counter(
            chunk.get("metadata", {}).get("source_kind", "rule")
            for chunk in chunks
        )

        return {
            "page_count": page_count,
            "chunk_count": len(chunks),
            "low_quality_chunk_count": chunk_stats.get("low_quality_chunk_count", 0),
            "low_quality_chunks": chunk_stats.get("low_quality_chunks", []),
            "chunks_per_page": chunk_stats.get("page_chunk_counts", {}),
            "rule_type_counts": dict(rule_type_counts),
            "rule_scope_counts": dict(rule_scope_counts),
            "source_kind_counts": dict(source_kind_counts),
            "rule_types_per_page": chunk_stats.get("page_type_counts", {}),
            "empty_text_pages": empty_pages,
            "suspicious_pages": suspicious_pages,
            "embedding": {
                "attempted": embedding_attempted,
                "success": embedding_success,
                "error": embedding_error,
            },
            "eval": {
                "available": False,
                "pass_rate": None,
                "summary": "No stable eval set has been run for this document yet.",
            },
        }

    @staticmethod
    def build_from_chunk_rows(
        *,
        page_count: int,
        cleaned_text: str,
        rows: List,
        embedding_attempted: bool,
        embedding_success: bool,
        embedding_error: Optional[str] = None,
    ) -> Dict:
        chunks = []
        low_quality_chunks = []
        page_chunk_counts: Dict[str, int] = {}
        page_type_counts: Dict[str, Dict[str, int]] = {}

        for row in rows:
            text = row["content"]
            page_match = re.search(r"\[Page\s+(\d+)\]", text)
            page = page_match.group(1) if page_match else "unknown"
            rule_type = row["rule_type"] or "text"
            rule_scope = row["rule_scope"] if "rule_scope" in row.keys() and row["rule_scope"] else "base"
            source_kind = row["source_kind"] if "source_kind" in row.keys() and row["source_kind"] else "rule"
            chunks.append({
                "text": text,
                "metadata": {
                    "page": page,
                    "type": rule_type,
                    "rule_scope": rule_scope,
                    "source_kind": source_kind,
                },
            })
            low_quality_reasons = TextChunker._low_quality_reasons(text)
            if low_quality_reasons:
                low_quality_chunks.append({
                    "page": int(page) if str(page).isdigit() else page,
                    "section": row["section_title"] if "section_title" in row.keys() else None,
                    "type": rule_type,
                    "source_kind": source_kind,
                    "reasons": low_quality_reasons,
                    "preview": TextChunker._preview_text(text),
                })
            page_chunk_counts[page] = page_chunk_counts.get(page, 0) + 1
            page_type_counts.setdefault(page, {})
            page_type_counts[page][rule_type] = page_type_counts[page].get(rule_type, 0) + 1

        return ProcessingReport.build(
            page_count=page_count,
            cleaned_text=cleaned_text,
            chunks=chunks,
            chunk_stats={
                "low_quality_chunk_count": len(low_quality_chunks),
                "low_quality_chunks": low_quality_chunks,
                "page_chunk_counts": page_chunk_counts,
                "page_type_counts": page_type_counts,
            },
            embedding_attempted=embedding_attempted,
            embedding_success=embedding_success,
            embedding_error=embedding_error,
        )

    @staticmethod
    def save(game_id: int, document_id: int, report: Dict) -> None:
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO processing_reports (game_id, document_id, report_json)
            VALUES (?, ?, ?)
            """,
            (game_id, document_id, json.dumps(report, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def latest_for_document(document_id: int) -> Optional[Dict]:
        conn = get_db_connection()
        row = conn.execute(
            """
            SELECT report_json
            FROM processing_reports
            WHERE document_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (document_id,),
        ).fetchone()
        conn.close()
        return json.loads(row["report_json"]) if row else None

    @staticmethod
    def latest_for_game(game_id: int) -> Dict[int, Dict]:
        conn = get_db_connection()
        rows = conn.execute(
            """
            SELECT pr.document_id, pr.report_json
            FROM processing_reports pr
            JOIN (
                SELECT document_id, MAX(id) AS max_id
                FROM processing_reports
                WHERE game_id = ?
                GROUP BY document_id
            ) latest ON latest.max_id = pr.id
            ORDER BY pr.created_at DESC, pr.id DESC
            """,
            (game_id,),
        ).fetchall()
        conn.close()
        return {row["document_id"]: json.loads(row["report_json"]) for row in rows}

    @staticmethod
    def attach_eval_summary(game_id: int, eval_summary: Dict) -> None:
        reports = ProcessingReport.latest_for_game(game_id)
        if not reports:
            return
        for document_id, report in reports.items():
            report["eval"] = eval_summary
            ProcessingReport.save(game_id, document_id, report)

    @staticmethod
    def _page_texts(cleaned_text: str) -> Dict[str, str]:
        return {
            str(page): text
            for page, text in TextChunker._iter_pages(cleaned_text)
        }

    @staticmethod
    def _suspicious_pages(page_texts: Dict[str, str]) -> List[Dict]:
        suspicious = []
        for page, text in page_texts.items():
            stripped = text.strip()
            if not stripped:
                continue

            reasons = []
            alpha_chars = sum(1 for ch in stripped if ch.isalpha())
            alpha_ratio = alpha_chars / max(len(stripped), 1)
            pipe_count = stripped.count("|")
            replacement_count = stripped.count("\ufffd")
            mojibake_count = len(re.findall(r"[ÃÂ�]{2,}|鈥|锛|涓|濡|瀹|鎴", stripped))
            repeated_symbols = len(re.findall(r"[^\w\s]{4,}", stripped))

            if len(stripped) > 160 and alpha_ratio < 0.22:
                reasons.append("low_alpha_ratio")
            if pipe_count > 25:
                reasons.append("many_table_pipes")
            if replacement_count > 3:
                reasons.append("replacement_characters")
            if mojibake_count > 5:
                reasons.append("mojibake_markers")
            if repeated_symbols > 4:
                reasons.append("repeated_symbol_runs")

            if reasons:
                suspicious.append({
                    "page": int(page) if page.isdigit() else page,
                    "reasons": reasons,
                    "alpha_ratio": round(alpha_ratio, 3),
                    "text_length": len(stripped),
                })

        return suspicious
