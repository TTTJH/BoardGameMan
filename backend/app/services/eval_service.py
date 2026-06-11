"""Stable retrieval evaluation for prepared rulebooks."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from app.database import get_db_connection, init_db
from app.services.ai_service import AIService
from app.services.processing_report import ProcessingReport
from app.services.vector_store import VectorStore


class EvalService:
    """Manage stable eval cases and retrieval-quality runs."""

    PASS_TERM_COVERAGE = 0.6
    FAILURE_TYPES = {
        "unreviewed",
        "bad_eval_case",
        "pdf_parse_noise",
        "chunk_boundary",
        "retrieval_miss",
        "term_too_strict",
        "variant_noise",
        "accepted",
    }

    @staticmethod
    def candidate_path(game_id: int) -> Path:
        return Path(__file__).resolve().parents[2] / "evals" / "candidates" / f"game_{game_id}_candidate_questions.json"

    @staticmethod
    def promote_candidates(game_id: int) -> Dict[str, Any]:
        path = EvalService.candidate_path(game_id)
        if not path.exists():
            raise ValueError(f"No candidate file found for game {game_id}. Generate candidates first.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list):
            raise ValueError("Candidate file is invalid.")

        init_db()
        conn = get_db_connection()
        inserted = 0
        updated = 0
        for item in candidates:
            case_id = str(item.get("id", "")).strip()
            question = str(item.get("question", "")).strip()
            if not case_id or not question:
                continue
            expected_pages = EvalService._json_list(item.get("expected_pages", []))
            expected_terms = EvalService._json_list(item.get("expected_terms", []))
            existing = conn.execute("SELECT id FROM eval_cases WHERE id = ?", (case_id,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE eval_cases
                    SET question = ?, expected_pages = ?, expected_terms = ?, evidence_quote = ?,
                        category = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        question,
                        expected_pages,
                        expected_terms,
                        str(item.get("evidence_quote", "")).strip(),
                        str(item.get("category", "action")).strip() or "action",
                        str(item.get("review_notes", "")).strip(),
                        case_id,
                    ),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO eval_cases
                    (id, game_id, question, expected_pages, expected_terms, evidence_quote, category, notes, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        case_id,
                        game_id,
                        question,
                        expected_pages,
                        expected_terms,
                        str(item.get("evidence_quote", "")).strip(),
                        str(item.get("category", "action")).strip() or "action",
                        str(item.get("review_notes", "")).strip(),
                    ),
                )
                inserted += 1
        conn.commit()
        total = conn.execute(
            "SELECT COUNT(*) AS count FROM eval_cases WHERE game_id = ?",
            (game_id,),
        ).fetchone()["count"]
        conn.close()
        return {"inserted": inserted, "updated": updated, "total": total, "candidate_path": str(path)}

    @staticmethod
    def list_cases(game_id: int, enabled_only: bool = False) -> List[Dict[str, Any]]:
        init_db()
        conn = get_db_connection()
        where = "WHERE game_id = ?"
        params: list[Any] = [game_id]
        if enabled_only:
            where += " AND enabled = 1"
        rows = conn.execute(
            f"""
            SELECT *
            FROM eval_cases
            {where}
            ORDER BY category, created_at, id
            """,
            params,
        ).fetchall()
        conn.close()
        return [EvalService._case_row(row) for row in rows]

    @staticmethod
    def update_case(case_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        failure_type = payload.get("failure_type")
        if failure_type is not None and failure_type not in EvalService.FAILURE_TYPES:
            raise ValueError(f"Invalid failure_type. Allowed values: {', '.join(sorted(EvalService.FAILURE_TYPES))}")

        init_db()
        conn = get_db_connection()
        existing = conn.execute("SELECT * FROM eval_cases WHERE id = ?", (case_id,)).fetchone()
        if not existing:
            conn.close()
            raise ValueError("Eval case not found.")

        enabled = payload.get("enabled")
        review_notes = payload.get("review_notes")
        expected_pages = payload.get("expected_pages")
        expected_terms = payload.get("expected_terms")
        conn.execute(
            """
            UPDATE eval_cases
            SET enabled = COALESCE(?, enabled),
                failure_type = COALESCE(?, failure_type),
                review_notes = COALESCE(?, review_notes),
                expected_pages = COALESCE(?, expected_pages),
                expected_terms = COALESCE(?, expected_terms),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                None if enabled is None else 1 if enabled else 0,
                failure_type,
                review_notes,
                None if expected_pages is None else EvalService._json_list(expected_pages),
                None if expected_terms is None else EvalService._json_list(expected_terms),
                case_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM eval_cases WHERE id = ?", (case_id,)).fetchone()
        conn.close()
        return EvalService._case_row(row)

    @staticmethod
    def latest_run(game_id: int, mode: str | None = None) -> Dict[str, Any] | None:
        init_db()
        conn = get_db_connection()
        where = "WHERE game_id = ?"
        params: list[Any] = [game_id]
        if mode:
            where += " AND COALESCE(mode, 'retrieval') = ?"
            params.append(mode)
        run = conn.execute(
            f"""
            SELECT *
            FROM eval_runs
            {where}
            ORDER BY id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        if not run:
            conn.close()
            return None
        results = conn.execute(
            """
            SELECT er.*, ec.question, ec.category, ec.enabled, ec.failure_type, ec.review_notes,
                   ec.expected_terms AS case_expected_terms
            FROM eval_results er
            JOIN eval_cases ec ON ec.id = er.case_id
            WHERE er.run_id = ?
            ORDER BY er.passed ASC, er.term_coverage ASC, er.id
            """,
            (run["id"],),
        ).fetchall()
        conn.close()
        return EvalService._run_response(run, results)

    @staticmethod
    def failure_analysis(game_id: int, mode: str | None = "retrieval") -> Dict[str, Any]:
        latest = EvalService.latest_run(game_id, mode=mode)
        if not latest or latest.get("available") is False:
            return {"available": False, "summary": "No eval run available for analysis."}

        results = latest.get("results", [])
        failures = [item for item in results if not item.get("passed")]
        suggested_counts = Counter(item.get("suggested_failure_type", "unreviewed") for item in failures)
        marked_counts = Counter(item.get("failure_type", "unreviewed") for item in failures)
        missing_terms = Counter()
        missed_expected_pages = Counter()
        frequent_found_pages = Counter()
        frequent_wrong_sections = Counter()

        for item in failures:
            expected_pages = set(item.get("expected_pages", []))
            found_pages = set(item.get("found_pages", []))
            for page in expected_pages - found_pages:
                missed_expected_pages[page] += 1
            for page in found_pages:
                frequent_found_pages[page] += 1
            for term in item.get("missing_terms", []):
                missing_terms[term] += 1
            for top in item.get("diagnostics", {}).get("top_results", [])[:3]:
                section = top.get("section") or top.get("rule_type") or "unknown"
                frequent_wrong_sections[section] += 1

        actions = EvalService._analysis_actions(suggested_counts, missing_terms)
        return {
            "available": True,
            "game_id": game_id,
            "mode": latest.get("mode", mode),
            "run_id": latest.get("id"),
            "case_count": latest.get("case_count", len(results)),
            "failed_count": len(failures),
            "pass_rate": latest.get("pass_rate", 0),
            "suggested_failure_counts": dict(suggested_counts),
            "marked_failure_counts": dict(marked_counts),
            "missed_expected_pages": EvalService._counter_items(missed_expected_pages),
            "frequent_found_pages": EvalService._counter_items(frequent_found_pages),
            "frequent_missing_terms": EvalService._counter_items(missing_terms),
            "frequent_top_sections": EvalService._counter_items(frequent_wrong_sections),
            "actions": actions,
        }

    @staticmethod
    def run(game_id: int, top_k: int = 8) -> Dict[str, Any]:
        cases = EvalService.list_cases(game_id, enabled_only=True)
        if not cases:
            raise ValueError("No enabled stable eval cases. Generate and promote candidates first.")

        store = VectorStore()
        results = []
        for case in cases:
            search_results = store.search(game_id, case["question"], top_k=top_k)
            docs = [doc for doc, _score in search_results]
            found_pages = EvalService._found_pages(docs)
            expected_pages = case["expected_pages"]
            source_hit = not expected_pages or bool(set(expected_pages) & set(found_pages))
            term_coverage, missing_terms = EvalService._term_coverage(docs, case["expected_terms"])
            passed = bool(source_hit and term_coverage >= EvalService.PASS_TERM_COVERAGE)
            results.append({
                "case_id": case["id"],
                "question": case["question"],
                "category": case["category"],
                "passed": passed,
                "source_hit": source_hit,
                "term_coverage": term_coverage,
                "expected_pages": expected_pages,
                "found_pages": found_pages,
                "missing_terms": missing_terms,
                "diagnostics": store.explain_results(case["question"], search_results),
                "top_sources": [
                    {
                        "page": EvalService._first_page(doc),
                        "excerpt": AIService.clean_source_excerpt(doc, case["question"], max_chars=360),
                    }
                    for doc in docs[:3]
                ],
            })

        case_count = len(results)
        passed_count = sum(1 for item in results if item["passed"])
        source_hits = sum(1 for item in results if item["source_hit"])
        coverage_values = [item["term_coverage"] for item in results]
        summary = {
            "available": True,
            "case_count": case_count,
            "passed_count": passed_count,
            "pass_rate": passed_count / case_count if case_count else 0,
            "source_hit_rate": source_hits / case_count if case_count else 0,
            "term_coverage_avg": mean(coverage_values) if coverage_values else 0,
            "summary": f"{passed_count}/{case_count} stable eval cases passed.",
        }

        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO eval_runs
            (game_id, case_count, passed_count, pass_rate, source_hit_rate, term_coverage_avg, summary_json, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                summary["case_count"],
                summary["passed_count"],
                summary["pass_rate"],
                summary["source_hit_rate"],
                summary["term_coverage_avg"],
                json.dumps(summary, ensure_ascii=False),
                "retrieval",
            ),
        )
        run_id = cursor.lastrowid
        for item in results:
            cursor.execute(
                """
                INSERT INTO eval_results
                (run_id, case_id, passed, source_hit, term_coverage, expected_pages,
                 found_pages, missing_terms, top_sources)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item["case_id"],
                    1 if item["passed"] else 0,
                    1 if item["source_hit"] else 0,
                    item["term_coverage"],
                    json.dumps(item["expected_pages"], ensure_ascii=False),
                    json.dumps(item["found_pages"], ensure_ascii=False),
                    json.dumps(item["missing_terms"], ensure_ascii=False),
                    json.dumps({
                        "sources": item["top_sources"],
                        "diagnostics": item.get("diagnostics", {}),
                    }, ensure_ascii=False),
                ),
            )
        conn.commit()
        run = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()
        rows = conn.execute(
            """
            SELECT er.*, ec.question, ec.category, ec.enabled, ec.failure_type, ec.review_notes,
                   ec.expected_terms AS case_expected_terms
            FROM eval_results er
            JOIN eval_cases ec ON ec.id = er.case_id
            WHERE er.run_id = ?
            ORDER BY er.passed ASC, er.term_coverage ASC, er.id
            """,
            (run_id,),
        ).fetchall()
        conn.close()

        ProcessingReport.attach_eval_summary(game_id, summary)
        return EvalService._run_response(run, rows)

    @staticmethod
    def run_chat(game_id: int, top_k: int = 8, max_cases: int = 10) -> Dict[str, Any]:
        cases = EvalService.list_cases(game_id, enabled_only=True)[:max_cases]
        if not cases:
            raise ValueError("No enabled stable eval cases. Generate and promote candidates first.")

        game_name = EvalService._game_name(game_id)
        store = VectorStore()
        ai_service = AIService()
        results = []

        for case in cases:
            search_results = store.search(game_id, case["question"], top_k=top_k)
            docs = [doc for doc, _score in search_results]
            found_pages = EvalService._found_pages(docs)
            expected_pages = case["expected_pages"]
            source_hit = not expected_pages or bool(set(expected_pages) & set(found_pages))
            retrieval_term_coverage, retrieval_missing_terms = EvalService._term_coverage(docs, case["expected_terms"])

            answer, source_indices = ai_service.generate_response(
                user_query=case["question"],
                context_documents=docs,
                game_name=game_name,
            )
            cited_docs = [
                docs[index]
                for index in source_indices
                if isinstance(index, int) and 0 <= index < len(docs)
            ]
            cited_pages = EvalService._found_pages(cited_docs)
            cited_source_hit = not expected_pages or bool(set(expected_pages) & set(cited_pages))
            displayed_source_hit = cited_source_hit or source_hit
            answer_term_coverage, answer_missing_terms = EvalService._term_coverage([answer], case["expected_terms"])
            effective_answer_coverage = EvalService._effective_answer_coverage(
                answer=answer,
                answer_term_coverage=answer_term_coverage,
                retrieval_term_coverage=retrieval_term_coverage,
                displayed_source_hit=displayed_source_hit,
            )
            passed = bool(displayed_source_hit and effective_answer_coverage >= EvalService.PASS_TERM_COVERAGE)
            results.append({
                "case_id": case["id"],
                "question": case["question"],
                "category": case["category"],
                "passed": passed,
                "source_hit": source_hit,
                "term_coverage": retrieval_term_coverage,
                "expected_pages": expected_pages,
                "found_pages": found_pages,
                "missing_terms": retrieval_missing_terms,
                "assistant_answer": answer,
                "answer_term_coverage": effective_answer_coverage,
                "answer_missing_terms": answer_missing_terms if effective_answer_coverage == answer_term_coverage else [],
                "cited_source_hit": displayed_source_hit,
                "diagnostics": store.explain_results(case["question"], search_results),
                "top_sources": [
                    {
                        "page": EvalService._first_page(doc),
                        "excerpt": AIService.clean_source_excerpt(doc, case["question"], max_chars=360),
                    }
                    for doc in docs[:3]
                ],
            })

        case_count = len(results)
        passed_count = sum(1 for item in results if item["passed"])
        source_hits = sum(1 for item in results if item["source_hit"])
        cited_hits = sum(1 for item in results if item["cited_source_hit"])
        answer_coverages = [item["answer_term_coverage"] for item in results]
        retrieval_coverages = [item["term_coverage"] for item in results]
        summary = {
            "available": True,
            "mode": "chat",
            "case_count": case_count,
            "passed_count": passed_count,
            "pass_rate": passed_count / case_count if case_count else 0,
            "source_hit_rate": source_hits / case_count if case_count else 0,
            "cited_source_hit_rate": cited_hits / case_count if case_count else 0,
            "term_coverage_avg": mean(retrieval_coverages) if retrieval_coverages else 0,
            "answer_term_coverage_avg": mean(answer_coverages) if answer_coverages else 0,
            "summary": f"{passed_count}/{case_count} chat eval cases passed.",
        }

        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO eval_runs
            (game_id, case_count, passed_count, pass_rate, source_hit_rate, term_coverage_avg, summary_json, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                summary["case_count"],
                summary["passed_count"],
                summary["pass_rate"],
                summary["source_hit_rate"],
                summary["term_coverage_avg"],
                json.dumps(summary, ensure_ascii=False),
                "chat",
            ),
        )
        run_id = cursor.lastrowid
        for item in results:
            cursor.execute(
                """
                INSERT INTO eval_results
                (run_id, case_id, passed, source_hit, term_coverage, expected_pages,
                 found_pages, missing_terms, top_sources, assistant_answer,
                 answer_term_coverage, answer_missing_terms, cited_source_hit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item["case_id"],
                    1 if item["passed"] else 0,
                    1 if item["source_hit"] else 0,
                    item["term_coverage"],
                    json.dumps(item["expected_pages"], ensure_ascii=False),
                    json.dumps(item["found_pages"], ensure_ascii=False),
                    json.dumps(item["missing_terms"], ensure_ascii=False),
                    json.dumps({
                        "sources": item["top_sources"],
                        "diagnostics": item.get("diagnostics", {}),
                    }, ensure_ascii=False),
                    item["assistant_answer"],
                    item["answer_term_coverage"],
                    json.dumps(item["answer_missing_terms"], ensure_ascii=False),
                    1 if item["cited_source_hit"] else 0,
                ),
            )
        conn.commit()
        run = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()
        rows = conn.execute(
            """
            SELECT er.*, ec.question, ec.category, ec.enabled, ec.failure_type, ec.review_notes,
                   ec.expected_terms AS case_expected_terms
            FROM eval_results er
            JOIN eval_cases ec ON ec.id = er.case_id
            WHERE er.run_id = ?
            ORDER BY er.passed ASC, COALESCE(er.answer_term_coverage, er.term_coverage) ASC, er.id
            """,
            (run_id,),
        ).fetchall()
        conn.close()

        ProcessingReport.attach_eval_summary(game_id, summary)
        return EvalService._run_response(run, rows)

    @staticmethod
    def _case_row(row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "game_id": row["game_id"],
            "question": row["question"],
            "expected_pages": EvalService._loads(row["expected_pages"]),
            "expected_terms": EvalService._loads(row["expected_terms"]),
            "evidence_quote": row["evidence_quote"] or "",
            "category": row["category"] or "action",
            "notes": row["notes"] or "",
            "enabled": bool(row["enabled"]),
            "failure_type": row["failure_type"] if "failure_type" in row.keys() and row["failure_type"] else "unreviewed",
            "review_notes": row["review_notes"] if "review_notes" in row.keys() and row["review_notes"] else "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _run_response(run, results) -> Dict[str, Any]:
        summary = EvalService._loads(run["summary_json"])
        return {
            "id": run["id"],
            "game_id": run["game_id"],
            "created_at": run["created_at"],
            "mode": run["mode"] if "mode" in run.keys() and run["mode"] else "retrieval",
            **summary,
            "results": [
                EvalService._result_row_response(row)
                for row in results
            ],
        }

    @staticmethod
    def _result_row_response(row) -> Dict[str, Any]:
        payload = EvalService._loads(row["top_sources"])
        if isinstance(payload, dict):
            top_sources = payload.get("sources", [])
            diagnostics = payload.get("diagnostics", {})
        else:
            top_sources = payload if isinstance(payload, list) else []
            diagnostics = {}

        result = {
            "case_id": row["case_id"],
            "question": row["question"],
            "category": row["category"],
            "enabled": bool(row["enabled"]) if "enabled" in row.keys() else True,
            "failure_type": row["failure_type"] if "failure_type" in row.keys() and row["failure_type"] else "unreviewed",
            "review_notes": row["review_notes"] if "review_notes" in row.keys() and row["review_notes"] else "",
            "passed": bool(row["passed"]),
            "source_hit": bool(row["source_hit"]),
            "term_coverage": row["term_coverage"],
            "expected_pages": EvalService._loads(row["expected_pages"]),
            "expected_terms": EvalService._loads(row["case_expected_terms"]) if "case_expected_terms" in row.keys() else [],
            "found_pages": EvalService._loads(row["found_pages"]),
            "missing_terms": EvalService._loads(row["missing_terms"]),
            "top_sources": top_sources,
            "diagnostics": diagnostics,
            "assistant_answer": row["assistant_answer"] if "assistant_answer" in row.keys() else None,
            "answer_term_coverage": row["answer_term_coverage"] if "answer_term_coverage" in row.keys() else None,
            "answer_missing_terms": EvalService._loads(row["answer_missing_terms"]) if "answer_missing_terms" in row.keys() else [],
            "cited_source_hit": bool(row["cited_source_hit"]) if "cited_source_hit" in row.keys() and row["cited_source_hit"] is not None else None,
        }
        result["suggested_failure_type"] = EvalService._suggest_failure_type(result)
        return result

    @staticmethod
    def _suggest_failure_type(result: Dict[str, Any]) -> str:
        if result["passed"]:
            return "accepted"
        query = (result.get("question") or "").lower()
        variant_query = any(term in query for term in ["单人", "solo", "variant", "变体", "扩展", "团队"])
        if variant_query and not result.get("source_hit"):
            return "variant_noise"
        if not result.get("source_hit"):
            return "retrieval_miss"
        if result.get("term_coverage", 0) < EvalService.PASS_TERM_COVERAGE:
            return "term_too_strict"
        if result.get("answer_term_coverage") is not None and result.get("answer_term_coverage", 0) < EvalService.PASS_TERM_COVERAGE:
            return "term_too_strict"
        return "unreviewed"

    @staticmethod
    def _analysis_actions(suggested_counts: Counter, missing_terms: Counter) -> List[str]:
        actions = []
        if suggested_counts.get("retrieval_miss", 0):
            actions.append("Expand query/topic rules for the most frequent missing terms and inspect top wrong sections.")
        if suggested_counts.get("variant_noise", 0):
            actions.append("Check rule_scope propagation and prefer variant chunks for solo/variant wording.")
        if suggested_counts.get("term_too_strict", 0):
            actions.append("Review expected_terms; replace brittle full phrases with stable rule concepts.")
        common_terms = [term for term, _count in missing_terms.most_common(3)]
        if common_terms:
            actions.append(f"Candidate query terms to add or normalize: {', '.join(common_terms)}.")
        return actions

    @staticmethod
    def _counter_items(counter: Counter, limit: int = 8) -> List[Dict[str, Any]]:
        return [
            {"value": value, "count": count}
            for value, count in counter.most_common(limit)
        ]

    @staticmethod
    def _game_name(game_id: int) -> str:
        init_db()
        conn = get_db_connection()
        row = conn.execute("SELECT name FROM games WHERE id = ?", (game_id,)).fetchone()
        conn.close()
        return row["name"] if row else f"Game {game_id}"

    @staticmethod
    def _found_pages(docs: List[str]) -> List[int]:
        pages = []
        for doc in docs:
            for match in re.findall(r"\[Page\s+(\d+)\]", doc or "", re.IGNORECASE):
                pages.append(int(match))
        return list(dict.fromkeys(pages))

    @staticmethod
    def _first_page(doc: str) -> int | None:
        match = re.search(r"\[Page\s+(\d+)\]", doc or "", re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _term_coverage(docs: List[str], expected_terms: List[str]) -> tuple[float, List[str]]:
        if not expected_terms:
            return 1.0, []
        haystack = " ".join(docs).lower()
        missing = [
            term
            for term in expected_terms
            if term and not EvalService._term_present(haystack, term)
        ]
        covered = len(expected_terms) - len(missing)
        return covered / max(len(expected_terms), 1), missing

    @staticmethod
    def _term_present(haystack: str, term: str) -> bool:
        normalized_term = term.lower().strip()
        if not normalized_term:
            return True
        if normalized_term in haystack:
            return True

        haystack_tokens = set(re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", haystack))
        term_tokens = [
            token
            for token in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", normalized_term)
            if token not in {"the", "a", "an", "to", "of", "on", "in", "at", "by", "or", "and", "s"}
        ]
        if not term_tokens:
            return False

        hits = sum(1 for token in term_tokens if token in haystack_tokens)
        if len(term_tokens) <= 2:
            return hits == len(term_tokens)
        return hits / len(term_tokens) >= 0.7

    @staticmethod
    def _effective_answer_coverage(
        answer: str,
        answer_term_coverage: float,
        retrieval_term_coverage: float,
        displayed_source_hit: bool,
    ) -> float:
        """Score localized answers without requiring English eval terms verbatim."""
        if answer_term_coverage >= EvalService.PASS_TERM_COVERAGE:
            return answer_term_coverage

        answer_text = (answer or "").lower()
        refusal_markers = [
            "not covered",
            "没有包含",
            "未包含",
            "没有提供",
            "无法确认",
            "无法根据",
            "not enough information",
        ]
        if any(marker in answer_text for marker in refusal_markers):
            return answer_term_coverage

        if displayed_source_hit and retrieval_term_coverage >= 0.8:
            return retrieval_term_coverage
        return answer_term_coverage

    @staticmethod
    def _json_list(value: Any) -> str:
        if not isinstance(value, list):
            value = []
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _loads(value: str | None) -> Any:
        if not value:
            return []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
