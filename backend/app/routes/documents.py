"""
Routes for document management and PDF upload
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, status
from typing import List
import json
import logging
import os
from pathlib import Path

from app.models import (
    ChunkResponse,
    ChunkSplitRequest,
    ChunkUpdate,
    DocumentResponse,
    DocumentUpdate,
    LayoutRegionCreate,
    LayoutRegionResponse,
    LayoutRegionUpdate,
)
from app.database import get_db_connection
from app.services.cover_generator import CoverGenerator
from app.services.glossary_service import GlossaryService
from app.services.pdf_processor import PDFProcessor, TextChunker
from app.services.pdf_visual_assets import PDFVisualAssets
from app.services.model_config import get_model_config
from app.services.processing_report import ProcessingReport
from app.services.vector_store import VectorStore
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
vector_store = VectorStore()

ALLOWED_RULE_TYPES = {
    "setup",
    "turn_structure",
    "action",
    "scoring",
    "end_game",
    "variant",
    "example",
    "component",
    "text",
}

ALLOWED_RULE_SCOPES = {"base", "variant", "example"}
ALLOWED_LAYOUT_REGION_TYPES = {
    "rule",
    "setup",
    "action",
    "scoring",
    "example",
    "component",
    "table",
    "variant",
    "ignore",
}
ALLOWED_DOCUMENT_SOURCE_TYPES = {
    "official_rulebook",
    "official_walkthrough",
    "official_faq",
    "official_errata",
    "official_tutorial",
    "community_qa",
    "player_guide",
    "house_rule",
}


def _infer_document_source_type(filename: str) -> str:
    name = (filename or "").lower()
    if any(term in name for term in ["walkthrough", "入门", "guide", "tutorial"]):
        return "official_walkthrough"
    if any(term in name for term in ["faq", "q&a", "qa"]):
        return "official_faq"
    if any(term in name for term in ["errata", "修订", "勘误"]):
        return "official_errata"
    if any(term in name for term in ["player", "玩家", "攻略"]):
        return "player_guide"
    return "official_rulebook"


def _row_value(row, key: str, default=None):
    return row[key] if key in row.keys() else default


def _loads_metadata(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _load_bbox(value: str | None) -> dict:
    if not value:
        return {"x": 0, "y": 0, "width": 1, "height": 1}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return {
                "x": float(parsed.get("x", 0)),
                "y": float(parsed.get("y", 0)),
                "width": float(parsed.get("width", 1)),
                "height": float(parsed.get("height", 1)),
            }
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {"x": 0, "y": 0, "width": 1, "height": 1}


def _int_or_none(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rule_unit_fields(chunk_text: str, metadata: dict) -> dict:
    page = _int_or_none(metadata.get("page"))
    rule_type = metadata.get("type", "text")
    rule_scope = metadata.get("rule_scope") or TextChunker._detect_rule_scope(chunk_text, rule_type)
    source_kind = metadata.get("source_kind") or TextChunker._detect_source_kind(chunk_text, rule_type)
    return {
        "section_title": metadata.get("section") or None,
        "page_start": page,
        "page_end": page,
        "rule_scope": rule_scope if rule_scope in ALLOWED_RULE_SCOPES else "base",
        "source_kind": source_kind,
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
    }


def _chunk_response(row) -> ChunkResponse:
    return ChunkResponse(
        id=row["id"],
        document_id=row["document_id"],
        chunk_index=row["chunk_index"],
        content=row["content"],
        rule_type=row["rule_type"] or "text",
        enabled=bool(row["enabled"]),
        keywords=row["keywords"],
        section_title=_row_value(row, "section_title"),
        page_start=_row_value(row, "page_start"),
        page_end=_row_value(row, "page_end"),
        rule_scope=_row_value(row, "rule_scope", "base") or "base",
        source_kind=_row_value(row, "source_kind", "rule") or "rule",
        metadata=_loads_metadata(_row_value(row, "metadata_json")),
    )


def _document_game_id(cursor, document_id: int) -> int:
    row = cursor.execute(
        "SELECT game_id FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return row["game_id"]


def _document_response(row, report=None) -> DocumentResponse:
    return DocumentResponse(
        id=row["id"],
        game_id=row["game_id"],
        filename=row["filename"],
        file_size=row["file_size"],
        pages=row["pages"],
        status=row["status"],
        source_type=_row_value(row, "source_type", "official_rulebook") or "official_rulebook",
        processing_report=report,
        created_at=row["created_at"],
    )


def _layout_region_response(row) -> LayoutRegionResponse:
    return LayoutRegionResponse(
        id=row["id"],
        document_id=row["document_id"],
        page=row["page"],
        label=row["label"],
        region_type=row["region_type"] or "rule",
        reading_order=row["reading_order"] or 1,
        bbox=_load_bbox(row["bbox"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _layout_regions_for_document(cursor, document_id: int) -> list[dict]:
    rows = cursor.execute(
        """
        SELECT *
        FROM document_layout_regions
        WHERE document_id = ?
        ORDER BY page, reading_order, id
        """,
        (document_id,),
    ).fetchall()
    regions = []
    for row in rows:
        regions.append({
            "id": row["id"],
            "document_id": row["document_id"],
            "page": row["page"],
            "label": row["label"],
            "region_type": row["region_type"] or "rule",
            "reading_order": row["reading_order"] or 1,
            "bbox": _load_bbox(row["bbox"]),
            "enabled": bool(row["enabled"]),
        })
    return regions


def _validate_layout_region(document, payload) -> None:
    if payload.region_type not in ALLOWED_LAYOUT_REGION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid region_type. Allowed values: {', '.join(sorted(ALLOWED_LAYOUT_REGION_TYPES))}",
        )
    if payload.page < 1 or (document["pages"] and payload.page > document["pages"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page is out of range")
    bbox = payload.bbox.model_dump()
    if bbox["x"] + bbox["width"] > 1.001 or bbox["y"] + bbox["height"] > 1.001:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Region must stay inside the page")


def _renumber_document_chunks(cursor, document_id: int) -> None:
    rows = cursor.execute(
        """
        SELECT id
        FROM chunks
        WHERE document_id = ?
        ORDER BY chunk_index, id
        """,
        (document_id,),
    ).fetchall()
    for index, row in enumerate(rows):
        cursor.execute(
            """
            UPDATE chunks
            SET chunk_index = ?, embedding_id = ?
            WHERE id = ?
            """,
            (index, f"doc_{document_id}_chunk_{index}", row["id"]),
        )


def _merge_keywords(left: str | None, right: str | None) -> str | None:
    tokens = []
    for value in [left, right]:
        if not value:
            continue
        tokens.extend(part.strip() for part in value.split(",") if part.strip())
    merged = list(dict.fromkeys(tokens))
    return ", ".join(merged) if merged else None


def _save_current_processing_report(game_id: int, document_id: int) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    doc = cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    rows = cursor.execute(
        """
        SELECT *
        FROM chunks
        WHERE document_id = ?
        ORDER BY chunk_index
        """,
        (document_id,),
    ).fetchall()
    enabled_count = cursor.execute(
        "SELECT COUNT(*) AS count FROM chunks WHERE document_id = ? AND COALESCE(enabled, 1) = 1",
        (document_id,),
    ).fetchone()["count"]
    conn.close()

    report_conn = get_db_connection()
    report_cursor = report_conn.cursor()
    layout_regions = _layout_regions_for_document(report_cursor, document_id)
    report_conn.close()
    text, page_count = PDFProcessor.extract_text_from_pdf(doc["file_path"], layout_regions=layout_regions)
    cleaned_text = TextChunker.clean_text(text)
    embedding_attempted = bool(get_model_config()["embedding"]["api_key"])
    embedding_count = vector_store.document_vector_count(game_id, document_id)
    report = ProcessingReport.build_from_chunk_rows(
        page_count=page_count,
        cleaned_text=cleaned_text,
        rows=rows,
        embedding_attempted=embedding_attempted,
        embedding_success=embedding_attempted and embedding_count >= enabled_count,
        embedding_error=None if (not embedding_attempted) or embedding_count >= enabled_count else "Some enabled chunks do not have stored embeddings.",
    )
    ProcessingReport.save(game_id, document_id, report)


@router.post("/{game_id}/upload", response_model=DocumentResponse)
async def upload_document(game_id: int, file: UploadFile = File(...)):
    """Upload and process a PDF rulebook"""
    try:
        # Validate game exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        game_row = cursor.fetchone()
        if not game_row:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        # Validate file
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed"
            )
        
        # Save file
        file_path = os.path.join(settings.UPLOAD_DIR, f"game_{game_id}_{file.filename}")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        contents = await file.read()
        if len(contents) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds maximum allowed"
            )
        
        with open(file_path, 'wb') as f:
            f.write(contents)
        
        # Extract text from PDF
        text, page_count = PDFProcessor.extract_text_from_pdf(file_path)
        
        # Clean and chunk text with semantic awareness
        cleaned_text = TextChunker.clean_text(text)
        chunks, chunk_stats = TextChunker.chunk_text_with_stats(
            cleaned_text,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP
        )
        
        # Store document in database
        source_type = _infer_document_source_type(file.filename)
        cursor.execute(
            """INSERT INTO documents (game_id, filename, file_path, file_size, pages, status, source_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (game_id, file.filename, file_path, len(contents), page_count, 'completed', source_type)
        )
        conn.commit()
        document_id = cursor.lastrowid

        try:
            PDFVisualAssets.render_pages(game_id, document_id, file_path)
        except Exception as visual_error:
            logger.warning(f"Could not render PDF visual pages for document {document_id}: {visual_error}")
        
        # Store chunks in database and vector store
        chunk_ids = []
        chunk_dicts = []
        for i, chunk_dict in enumerate(chunks):
            chunk_id = f"doc_{document_id}_chunk_{i}"
            # Handle both dict and string formats
            if isinstance(chunk_dict, dict):
                chunk_text = chunk_dict.get("text", "")
                chunk_metadata = chunk_dict.get("metadata", {})
            else:
                chunk_text = chunk_dict
                chunk_metadata = {}
            
            # Skip empty chunks
            if not chunk_text or not chunk_text.strip():
                logger.warning(f"Skipping empty chunk {i} in document {document_id}")
                continue
            
            rule_type = chunk_metadata.get("type", "text")
            unit_fields = _rule_unit_fields(chunk_text, chunk_metadata)
            cursor.execute(
                """
                INSERT INTO chunks (
                    document_id, chunk_index, content, embedding_id, rule_type, enabled,
                    section_title, page_start, page_end, rule_scope, source_kind, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    i,
                    chunk_text,
                    chunk_id,
                    rule_type,
                    1,
                    unit_fields["section_title"],
                    unit_fields["page_start"],
                    unit_fields["page_end"],
                    unit_fields["rule_scope"],
                    unit_fields["source_kind"],
                    unit_fields["metadata_json"],
                )
            )
            chunk_ids.append(chunk_id)
            chunk_dicts.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })
        
        conn.commit()
        
        embedding_attempted = bool(get_model_config()["embedding"]["api_key"])
        embedding_success = False
        embedding_error = None

        # Add to vector store with metadata only if we have chunks
        if chunk_ids and chunk_dicts:
            try:
                vector_store.add_documents(game_id, chunk_dicts, chunk_ids)
                embedding_success = embedding_attempted
                logger.info(f"Added {len(chunk_ids)} chunks to vector store for document {document_id}")
            except Exception as vector_error:
                embedding_error = str(vector_error)
                logger.warning(f"Could not add chunks to vector store for document {document_id}: {vector_error}")
        else:
            logger.warning(f"No valid chunks to add to vector store for document {document_id}")

        report = ProcessingReport.build(
            page_count=page_count,
            cleaned_text=cleaned_text,
            chunks=chunks,
            chunk_stats=chunk_stats,
            embedding_attempted=embedding_attempted,
            embedding_success=embedding_success,
            embedding_error=embedding_error,
        )
        ProcessingReport.save(game_id, document_id, report)
        _regenerate_glossary(game_id)

        if not game_row["cover_url"]:
            try:
                cover_url = CoverGenerator.generate_for_game(
                    game_id=game_id,
                    game_name=game_row["name"],
                    pdf_text=cleaned_text,
                    filename=file.filename,
                )
                cursor.execute(
                    """
                    UPDATE games
                    SET cover_url = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND (cover_url IS NULL OR cover_url = '')
                    """,
                    (cover_url, game_id),
                )
                conn.commit()
                logger.info(f"Generated default cover for game {game_id}: {cover_url}")
            except Exception as cover_error:
                logger.warning(f"Could not generate default cover for game {game_id}: {cover_error}")
        
        # Fetch and return document
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        conn.close()
        
        logger.info(f"Successfully processed document {document_id} with {len(chunks)} chunks")
        
        return _document_response(row, report)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )


@router.get("/{game_id}", response_model=List[DocumentResponse])
async def list_documents(game_id: int):
    """List all documents for a game"""
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
        
        cursor.execute(
            "SELECT * FROM documents WHERE game_id = ? ORDER BY created_at DESC",
            (game_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        reports = ProcessingReport.latest_for_game(game_id)
        
        return [
            _document_response(row, reports.get(row["id"]))
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving documents"
        )


@router.post("/{document_id}/processing-report")
async def rebuild_processing_report(document_id: int):
    """Rebuild a processing report for an already-uploaded document."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        doc = cursor.fetchone()
        if not doc:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        layout_regions = _layout_regions_for_document(cursor, document_id)
        text, page_count = PDFProcessor.extract_text_from_pdf(doc["file_path"], layout_regions=layout_regions)
        cleaned_text = TextChunker.clean_text(text)
        chunks, chunk_stats = TextChunker.chunk_text_with_stats(
            cleaned_text,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )
        existing_rule_types = cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN rule_type IS NULL OR rule_type = 'text' THEN 1 ELSE 0 END) AS default_count
            FROM chunks
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()
        should_backfill_rule_types = (
            existing_rule_types["total"] > 0
            and existing_rule_types["total"] == (existing_rule_types["default_count"] or 0)
        )
        if should_backfill_rule_types:
            for chunk_index, chunk in enumerate(chunks):
                metadata = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                cursor.execute(
                    """
                    UPDATE chunks
                    SET rule_type = ?
                    WHERE document_id = ? AND chunk_index = ?
                    """,
                    (metadata.get("type", "text"), document_id, chunk_index),
                )
            conn.commit()

        enabled_count = cursor.execute(
            "SELECT COUNT(*) AS count FROM chunks WHERE document_id = ? AND COALESCE(enabled, 1) = 1",
            (document_id,),
        ).fetchone()["count"]
        chunk_rows = cursor.execute(
            """
            SELECT *
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (document_id,),
        ).fetchall()
        conn.close()

        embedding_attempted = bool(get_model_config()["embedding"]["api_key"])
        embedding_count = vector_store.document_vector_count(doc["game_id"], document_id)
        report = ProcessingReport.build_from_chunk_rows(
            page_count=page_count,
            cleaned_text=cleaned_text,
            rows=chunk_rows,
            embedding_attempted=embedding_attempted,
            embedding_success=embedding_attempted and embedding_count >= enabled_count,
            embedding_error=None if (not embedding_attempted) or embedding_count >= enabled_count else "Some enabled chunks do not have stored embeddings.",
        )
        if chunk_stats.get("low_quality_chunks"):
            report["low_quality_chunk_count"] = chunk_stats.get("low_quality_chunk_count", 0)
            report["low_quality_chunks"] = chunk_stats.get("low_quality_chunks", [])
        ProcessingReport.save(doc["game_id"], document_id, report)
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rebuilding processing report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rebuilding processing report: {str(e)}"
        )


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(document_id: int):
    """Re-extract, re-chunk, and re-index an existing PDF with the current mixer."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        doc = cursor.fetchone()
        if not doc:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        layout_regions = _layout_regions_for_document(cursor, document_id)
        text, page_count = PDFProcessor.extract_text_from_pdf(doc["file_path"], layout_regions=layout_regions)
        cleaned_text = TextChunker.clean_text(text)
        chunks, chunk_stats = TextChunker.chunk_text_with_stats(
            cleaned_text,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )

        vector_store.delete_document_vectors(doc["game_id"], document_id)
        cursor.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        chunk_ids = []
        chunk_dicts = []
        for index, chunk_dict in enumerate(chunks):
            chunk_text = chunk_dict.get("text", "")
            if not chunk_text.strip():
                continue
            metadata = chunk_dict.get("metadata", {})
            unit_fields = _rule_unit_fields(chunk_text, metadata)
            embedding_id = f"doc_{document_id}_chunk_{index}"
            cursor.execute(
                """
                INSERT INTO chunks (
                    document_id, chunk_index, content, embedding_id, rule_type, enabled, keywords,
                    section_title, page_start, page_end, rule_scope, source_kind, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    index,
                    chunk_text,
                    embedding_id,
                    metadata.get("type", "text"),
                    1,
                    None,
                    unit_fields["section_title"],
                    unit_fields["page_start"],
                    unit_fields["page_end"],
                    unit_fields["rule_scope"],
                    unit_fields["source_kind"],
                    unit_fields["metadata_json"],
                ),
            )
            chunk_ids.append(embedding_id)
            chunk_dicts.append({
                "text": chunk_text,
                "metadata": metadata,
            })

        cursor.execute(
            """
            UPDATE documents
            SET pages = ?, status = ?
            WHERE id = ?
            """,
            (page_count, "completed", document_id),
        )
        conn.commit()

        embedding_attempted = bool(get_model_config()["embedding"]["api_key"])
        embedding_success = False
        embedding_error = None
        if chunk_ids and chunk_dicts:
            try:
                vector_store.add_documents(doc["game_id"], chunk_dicts, chunk_ids)
                embedding_success = embedding_attempted
            except Exception as vector_error:
                embedding_error = str(vector_error)
                logger.warning(f"Could not re-index document {document_id}: {vector_error}")

        report = ProcessingReport.build(
            page_count=page_count,
            cleaned_text=cleaned_text,
            chunks=chunks,
            chunk_stats=chunk_stats,
            embedding_attempted=embedding_attempted,
            embedding_success=embedding_success,
            embedding_error=embedding_error,
        )
        ProcessingReport.save(doc["game_id"], document_id, report)
        _regenerate_glossary(doc["game_id"])

        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        updated_doc = cursor.fetchone()
        conn.close()
        return _document_response(updated_doc, report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reprocessing document: {str(e)}"
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(document_id: int, payload: DocumentUpdate):
    """Update document metadata such as source type."""
    if payload.source_type not in ALLOWED_DOCUMENT_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type. Allowed values: {', '.join(sorted(ALLOWED_DOCUMENT_SOURCE_TYPES))}",
        )

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        cursor.execute(
            "UPDATE documents SET source_type = ? WHERE id = ?",
            (payload.source_type, document_id),
        )
        conn.commit()
        updated = cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        conn.close()
        return _document_response(updated, ProcessingReport.latest_for_document(document_id))
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Error updating document {document_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating document",
        )


@router.get("/{document_id}/layout-regions", response_model=List[LayoutRegionResponse])
async def list_layout_regions(document_id: int, page: int | None = Query(None, ge=1)):
    """List manual layout regions for a PDF document."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        doc = cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        if page is None:
            rows = cursor.execute(
                """
                SELECT *
                FROM document_layout_regions
                WHERE document_id = ?
                ORDER BY page, reading_order, id
                """,
                (document_id,),
            ).fetchall()
        else:
            rows = cursor.execute(
                """
                SELECT *
                FROM document_layout_regions
                WHERE document_id = ? AND page = ?
                ORDER BY reading_order, id
                """,
                (document_id, page),
            ).fetchall()
        conn.close()
        return [_layout_region_response(row) for row in rows]
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Error listing layout regions for document {document_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing layout regions",
        )


@router.post("/{document_id}/layout-regions", response_model=LayoutRegionResponse, status_code=status.HTTP_201_CREATED)
async def create_layout_region(document_id: int, payload: LayoutRegionCreate):
    """Create a manual layout region for a PDF page."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        doc = cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        _validate_layout_region(doc, payload)
        cursor.execute(
            """
            INSERT INTO document_layout_regions (
                document_id, page, label, region_type, reading_order, bbox, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                payload.page,
                payload.label.strip() if payload.label else None,
                payload.region_type,
                payload.reading_order,
                json.dumps(payload.bbox.model_dump(), ensure_ascii=False),
                1 if payload.enabled else 0,
            ),
        )
        region_id = cursor.lastrowid
        conn.commit()
        row = cursor.execute("SELECT * FROM document_layout_regions WHERE id = ?", (region_id,)).fetchone()
        conn.close()
        return _layout_region_response(row)
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Error creating layout region for document {document_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating layout region",
        )


@router.put("/layout-regions/{region_id}", response_model=LayoutRegionResponse)
async def update_layout_region(region_id: int, payload: LayoutRegionUpdate):
    """Update a manual layout region."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        region = cursor.execute(
            "SELECT * FROM document_layout_regions WHERE id = ?",
            (region_id,),
        ).fetchone()
        if not region:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout region not found")

        doc = cursor.execute("SELECT * FROM documents WHERE id = ?", (region["document_id"],)).fetchone()
        _validate_layout_region(doc, payload)
        cursor.execute(
            """
            UPDATE document_layout_regions
            SET label = ?, region_type = ?, reading_order = ?, bbox = ?, enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload.label.strip() if payload.label else None,
                payload.region_type,
                payload.reading_order,
                json.dumps(payload.bbox.model_dump(), ensure_ascii=False),
                1 if payload.enabled else 0,
                region_id,
            ),
        )
        conn.commit()
        row = cursor.execute("SELECT * FROM document_layout_regions WHERE id = ?", (region_id,)).fetchone()
        conn.close()
        return _layout_region_response(row)
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Error updating layout region {region_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating layout region",
        )


@router.delete("/layout-regions/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_layout_region(region_id: int):
    """Delete a manual layout region."""
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT id FROM document_layout_regions WHERE id = ?", (region_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout region not found")

        conn.execute("DELETE FROM document_layout_regions WHERE id = ?", (region_id,))
        conn.commit()
        conn.close()
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Error deleting layout region {region_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting layout region",
        )


def _regenerate_glossary(game_id: int) -> None:
    try:
        GlossaryService.regenerate_for_game(game_id)
    except Exception as glossary_error:
        logger.warning(f"Could not regenerate glossary for game {game_id}: {glossary_error}")


@router.get("/{document_id}/chunks", response_model=List[ChunkResponse])
async def list_document_chunks(document_id: int):
    """List chunks for manual inspection and correction."""
    try:
        conn = get_db_connection()
        rows = conn.execute(
            """
            SELECT *
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (document_id,),
        ).fetchall()
        conn.close()
        return [_chunk_response(row) for row in rows]
    except Exception as e:
        logger.error(f"Error listing chunks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing chunks"
        )


@router.put("/chunks/{chunk_id}", response_model=ChunkResponse)
async def update_chunk(chunk_id: int, chunk: ChunkUpdate):
    """Apply a manual correction to a chunk."""
    try:
        if chunk.rule_type not in ALLOWED_RULE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid rule_type. Allowed values: {', '.join(sorted(ALLOWED_RULE_TYPES))}"
            )
        if chunk.rule_scope not in ALLOWED_RULE_SCOPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid rule_scope. Allowed values: {', '.join(sorted(ALLOWED_RULE_SCOPES))}"
            )

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chunk not found"
            )
        game_id = _document_game_id(cursor, existing["document_id"])

        cursor.execute(
            """
            UPDATE chunks
            SET content = ?, rule_type = ?, enabled = ?, keywords = ?, section_title = ?, rule_scope = ?
            WHERE id = ?
            """,
            (
                chunk.content,
                chunk.rule_type,
                1 if chunk.enabled else 0,
                chunk.keywords,
                chunk.section_title,
                chunk.rule_scope,
                chunk_id,
            ),
        )
        conn.commit()
        cursor.execute(
            """
            SELECT *
            FROM chunks
            WHERE id = ?
            """,
            (chunk_id,),
        )
        row = cursor.fetchone()
        conn.close()
        vector_store.reindex_document(game_id, row["document_id"])
        _save_current_processing_report(game_id, row["document_id"])
        return _chunk_response(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chunk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating chunk"
        )


@router.post("/chunks/{chunk_id}/split", response_model=List[ChunkResponse])
async def split_chunk(chunk_id: int, payload: ChunkSplitRequest):
    """Split one chunk into two editable chunks and rebuild document vectors."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current = cursor.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        if not current:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chunk not found"
            )

        content = current["content"]
        if payload.split_at >= len(content):
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split position must be inside the chunk content"
            )

        left = content[:payload.split_at].strip()
        right = content[payload.split_at:].strip()
        if not left or not right:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split position must leave content on both sides"
            )

        game_id = _document_game_id(cursor, current["document_id"])
        cursor.execute(
            """
            UPDATE chunks
            SET content = ?
            WHERE id = ?
            """,
            (left, chunk_id),
        )
        cursor.execute(
            """
            INSERT INTO chunks (
                document_id, chunk_index, content, embedding_id, rule_type, enabled, keywords,
                section_title, page_start, page_end, rule_scope, source_kind, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current["document_id"],
                current["chunk_index"] + 1,
                right,
                "",
                current["rule_type"] or "text",
                current["enabled"],
                current["keywords"],
                _row_value(current, "section_title"),
                _row_value(current, "page_start"),
                _row_value(current, "page_end"),
                _row_value(current, "rule_scope", "base"),
                _row_value(current, "source_kind", "rule"),
                _row_value(current, "metadata_json"),
            ),
        )
        _renumber_document_chunks(cursor, current["document_id"])
        conn.commit()
        rows = cursor.execute(
            """
            SELECT *
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (current["document_id"],),
        ).fetchall()
        conn.close()
        vector_store.reindex_document(game_id, current["document_id"])
        _save_current_processing_report(game_id, current["document_id"])
        return [_chunk_response(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error splitting chunk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error splitting chunk"
        )


@router.post("/chunks/{chunk_id}/merge-next", response_model=List[ChunkResponse])
async def merge_chunk_with_next(chunk_id: int):
    """Merge a chunk with its next neighbor and rebuild document vectors."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current = cursor.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        if not current:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chunk not found"
            )

        next_chunk = cursor.execute(
            """
            SELECT *
            FROM chunks
            WHERE document_id = ? AND chunk_index > ?
            ORDER BY chunk_index
            LIMIT 1
            """,
            (current["document_id"], current["chunk_index"]),
        ).fetchone()
        if not next_chunk:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No next chunk to merge"
            )

        game_id = _document_game_id(cursor, current["document_id"])
        merged_content = "\n\n".join([current["content"].strip(), next_chunk["content"].strip()]).strip()
        merged_rule_type = current["rule_type"] or next_chunk["rule_type"] or "text"
        if merged_rule_type == "text" and next_chunk["rule_type"]:
            merged_rule_type = next_chunk["rule_type"]

        cursor.execute(
            """
            UPDATE chunks
            SET content = ?, rule_type = ?, enabled = ?, keywords = ?, section_title = ?, rule_scope = ?
            WHERE id = ?
            """,
            (
                merged_content,
                merged_rule_type,
                1 if (current["enabled"] or next_chunk["enabled"]) else 0,
                _merge_keywords(current["keywords"], next_chunk["keywords"]),
                _row_value(current, "section_title") or _row_value(next_chunk, "section_title"),
                _row_value(current, "rule_scope", "base") if _row_value(current, "rule_scope", "base") != "base" else _row_value(next_chunk, "rule_scope", "base"),
                current["id"],
            ),
        )
        cursor.execute("DELETE FROM chunks WHERE id = ?", (next_chunk["id"],))
        _renumber_document_chunks(cursor, current["document_id"])
        conn.commit()
        rows = cursor.execute(
            """
            SELECT *
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (current["document_id"],),
        ).fetchall()
        conn.close()
        vector_store.reindex_document(game_id, current["document_id"])
        _save_current_processing_report(game_id, current["document_id"])
        return [_chunk_response(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging chunk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error merging chunk"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int):
    """Delete a document"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get document info
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        doc = cursor.fetchone()
        
        if not doc:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        vector_store.delete_document_vectors(doc['game_id'], document_id)
        
        # Delete file
        if os.path.exists(doc['file_path']):
            os.remove(doc['file_path'])
        
        # Delete from database
        cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted document {document_id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting document"
        )
