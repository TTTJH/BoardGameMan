"""
Routes for manually curated game visual assets.
"""

from pathlib import Path
import json
import re
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.database import get_db_connection
from app.models import GameAssetCreate, GameAssetResponse, GameAssetUpdate
from app.services.pdf_visual_assets import PDFVisualAssets

router = APIRouter()


def asset_dir(game_id: int) -> Path:
    return Path(settings.UPLOAD_DIR) / "game_assets" / f"game_{game_id}"


def asset_url(game_id: int, filename: str) -> str:
    return f"/game-assets/game_{game_id}/{filename}"


def parse_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in value.split(",") if item.strip()]


def row_to_asset(row) -> GameAssetResponse:
    source_bbox = None
    if row["source_bbox"]:
        try:
            source_bbox = json.loads(row["source_bbox"])
        except json.JSONDecodeError:
            source_bbox = None
    return GameAssetResponse(
        id=row["id"],
        game_id=row["game_id"],
        document_id=row["document_id"],
        page=row["page"],
        name=row["name"],
        display_name=row["display_name"],
        asset_type=row["asset_type"] or "component",
        keywords=parse_keywords(row["keywords"]),
        image_url=row["image_path"],
        source_bbox=source_bbox,
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def safe_asset_filename(name: str, page: int) -> str:
    safe_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60] or "asset"
    return f"page_{page}_{safe_name}.png"


def unique_asset_path(game_id: int, name: str, page: int) -> Path:
    base = Path(safe_asset_filename(name, page)).stem
    return asset_dir(game_id) / f"{base}_hq_{uuid.uuid4().hex[:8]}.png"


def delete_asset_file(image_url: str | None) -> None:
    if not image_url or not image_url.startswith("/game-assets/game_"):
        return
    image_path = Path(settings.UPLOAD_DIR) / image_url.lstrip("/").replace("game-assets/", "game_assets/")
    try:
        if image_path.exists():
            image_path.unlink()
    except OSError:
        pass


def parse_source_bbox(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def get_document(game_id: int, document_id: int):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ? AND game_id = ?",
        (document_id, game_id),
    ).fetchone()
    conn.close()
    return row


def validate_document_page(document, page: int) -> None:
    if page < 1 or (document["pages"] and page > document["pages"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page is out of range")


def create_high_resolution_asset_image(
    game_id: int,
    document,
    page: int,
    name: str,
    asset_type: str,
    bbox: dict,
) -> str:
    output_path = unique_asset_path(game_id, name, page)
    try:
        PDFVisualAssets.crop_normalized_asset(
            file_path=document["file_path"],
            page_number=page,
            bbox=bbox,
            asset_type=asset_type,
            output_path=output_path,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not render high-resolution asset: {error}",
        ) from error
    return asset_url(game_id, output_path.name)


def ensure_page_image(game_id: int, document_id: int, page: int) -> Path:
    document = get_document(game_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if page < 1 or (document["pages"] and page > document["pages"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page is out of range")

    page_path = PDFVisualAssets.page_path(game_id, document_id, page)
    if not page_path.exists():
        PDFVisualAssets.render_pages(game_id, document_id, document["file_path"])
    if not page_path.exists():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not render PDF page")
    return page_path


@router.get("/{game_id}", response_model=list[GameAssetResponse])
async def list_assets(game_id: int, enabled_only: bool = False):
    conn = get_db_connection()
    if enabled_only:
        rows = conn.execute(
            "SELECT * FROM game_assets WHERE game_id = ? AND enabled = 1 ORDER BY updated_at DESC, id DESC",
            (game_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM game_assets WHERE game_id = ? ORDER BY updated_at DESC, id DESC",
            (game_id,),
        ).fetchall()
    conn.close()
    return [row_to_asset(row) for row in rows]


@router.get("/{game_id}/page")
async def get_page_preview(
    game_id: int,
    document_id: int = Query(...),
    page: int = Query(..., ge=1),
):
    document = get_document(game_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    validate_document_page(document, page)
    try:
        PDFVisualAssets.render_page_preview(game_id, document_id, document["file_path"], page)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not render PDF page preview: {error}",
        ) from error
    return {
        "image_url": PDFVisualAssets.page_preview_url(game_id, document_id, page),
        "page": page,
        "document_id": document_id,
        "render_scale": PDFVisualAssets.ASSET_MANAGER_PREVIEW_SCALE,
        "base_scale": PDFVisualAssets.PAGE_PREVIEW_SCALE,
    }


@router.post("/{game_id}", response_model=GameAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(game_id: int, payload: GameAssetCreate):
    document = get_document(game_id, payload.document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    validate_document_page(document, payload.page)
    bbox = payload.bbox.model_dump()
    image_url = create_high_resolution_asset_image(
        game_id=game_id,
        document=document,
        page=payload.page,
        name=payload.name,
        asset_type=payload.asset_type,
        bbox=bbox,
    )
    keywords = json.dumps(payload.keywords, ensure_ascii=False)
    source_bbox = json.dumps(bbox, ensure_ascii=False)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO game_assets (
            game_id, document_id, page, name, display_name, asset_type,
            keywords, image_path, source_bbox, enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id,
            payload.document_id,
            payload.page,
            payload.name,
            payload.display_name,
            payload.asset_type,
            keywords,
            image_url,
            source_bbox,
            1 if payload.enabled else 0,
        ),
    )
    asset_id = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM game_assets WHERE id = ?", (asset_id,)).fetchone()
    conn.close()
    return row_to_asset(row)


@router.post("/{game_id}/regenerate")
async def regenerate_game_assets(game_id: int):
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT a.*, d.file_path, d.pages
        FROM game_assets a
        JOIN documents d ON d.id = a.document_id
        WHERE a.game_id = ?
        ORDER BY a.id
        """,
        (game_id,),
    ).fetchall()
    conn.close()

    regenerated = []
    failed = []
    for row in rows:
        bbox = parse_source_bbox(row["source_bbox"])
        if not bbox or not row["document_id"] or not row["page"]:
            failed.append({"id": row["id"], "name": row["name"], "error": "Missing source bbox"})
            continue
        try:
            document = {
                "id": row["document_id"],
                "file_path": row["file_path"],
                "pages": row["pages"],
            }
            validate_document_page(document, row["page"])
            image_url = create_high_resolution_asset_image(
                game_id=game_id,
                document=document,
                page=row["page"],
                name=row["name"],
                asset_type=row["asset_type"] or "component",
                bbox=bbox,
            )
            update_conn = get_db_connection()
            update_conn.execute(
                """
                UPDATE game_assets
                SET image_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (image_url, row["id"]),
            )
            update_conn.commit()
            update_conn.close()
            delete_asset_file(row["image_path"])
            regenerated.append({"id": row["id"], "name": row["name"], "image_url": image_url})
        except Exception as error:
            failed.append({"id": row["id"], "name": row["name"], "error": str(error)})

    return {
        "regenerated": regenerated,
        "failed": failed,
        "count": len(regenerated),
        "failed_count": len(failed),
    }


@router.post("/items/{asset_id}/regenerate", response_model=GameAssetResponse)
async def regenerate_asset(asset_id: int):
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT a.*, d.file_path, d.pages
        FROM game_assets a
        JOIN documents d ON d.id = a.document_id
        WHERE a.id = ?
        """,
        (asset_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    bbox = parse_source_bbox(row["source_bbox"])
    if not bbox or not row["document_id"] or not row["page"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset has no saved source bbox")

    document = {
        "id": row["document_id"],
        "file_path": row["file_path"],
        "pages": row["pages"],
    }
    validate_document_page(document, row["page"])
    image_url = create_high_resolution_asset_image(
        game_id=row["game_id"],
        document=document,
        page=row["page"],
        name=row["name"],
        asset_type=row["asset_type"] or "component",
        bbox=bbox,
    )
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE game_assets
        SET image_path = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (image_url, asset_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM game_assets WHERE id = ?", (asset_id,)).fetchone()
    conn.close()
    delete_asset_file(row["image_path"])
    return row_to_asset(updated)


@router.put("/{asset_id}", response_model=GameAssetResponse)
async def update_asset(asset_id: int, payload: GameAssetUpdate):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM game_assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    conn.execute(
        """
        UPDATE game_assets
        SET name = ?, display_name = ?, asset_type = ?, keywords = ?, enabled = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            payload.name,
            payload.display_name,
            payload.asset_type,
            json.dumps(payload.keywords, ensure_ascii=False),
            1 if payload.enabled else 0,
            asset_id,
        ),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM game_assets WHERE id = ?", (asset_id,)).fetchone()
    conn.close()
    return row_to_asset(updated)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(asset_id: int):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM game_assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    delete_asset_file(row["image_path"] or "")

    conn.execute("DELETE FROM game_assets WHERE id = ?", (asset_id,))
    conn.commit()
    conn.close()
