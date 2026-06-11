"""
Routes for game management
"""

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from typing import List
import logging
import os
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.models import GameCreate, GameResponse, GameUpdate
from app.database import get_db_connection
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter()
vector_store = VectorStore()
ALLOWED_COVER_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def game_response(row) -> GameResponse:
    rulebook_count = row["rulebook_count"] if "rulebook_count" in row.keys() else 0
    return GameResponse(
        id=row['id'],
        name=row['name'],
        description=row['description'],
        cover_url=row['cover_url'],
        rulebook_count=rulebook_count,
        is_ready=rulebook_count > 0,
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )


def select_game_sql(where_clause: str = "", order_clause: str = "") -> str:
    return f"""
        SELECT g.*, COUNT(d.id) AS rulebook_count
        FROM games g
        LEFT JOIN documents d ON d.game_id = g.id
        {where_clause}
        GROUP BY g.id
        {order_clause}
    """


@router.post("/", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
async def create_game(game: GameCreate):
    """Create a new board game"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO games (name, description) VALUES (?, ?)",
            (game.name, game.description)
        )
        conn.commit()
        game_id = cursor.lastrowid
        
        # Create vector store collection for this game
        vector_store.create_collection(game_id)
        
        cursor.execute(select_game_sql("WHERE g.id = ?"), (game_id,))
        row = cursor.fetchone()
        conn.close()
        
        return game_response(row)
    except Exception as e:
        logger.error(f"Error creating game: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[GameResponse])
async def list_games():
    """List all board games"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(select_game_sql(order_clause="ORDER BY g.created_at DESC"))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            game_response(row)
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error listing games: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving games"
        )


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: int):
    """Get a specific board game"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(select_game_sql("WHERE g.id = ?"), (game_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        return game_response(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting game: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving game"
        )


@router.put("/{game_id}", response_model=GameResponse)
async def update_game(game_id: int, game: GameUpdate):
    """Rename or update a board game's metadata."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM games WHERE id = ?", (game_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )

        cursor.execute(
            """
            UPDATE games
            SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (game.name, game.description, game_id)
        )
        conn.commit()
        cursor.execute(select_game_sql("WHERE g.id = ?"), (game_id,))
        row = cursor.fetchone()
        conn.close()
        return game_response(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating game: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{game_id}/cover", response_model=GameResponse)
async def upload_game_cover(game_id: int, file: UploadFile = File(...)):
    """Upload a custom cover image for a board game."""
    try:
        if file.content_type not in ALLOWED_COVER_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPG, PNG, and WEBP cover images are allowed"
            )

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(select_game_sql("WHERE g.id = ?"), (game_id,))
        game_row = cursor.fetchone()
        if not game_row:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )

        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Cover image size exceeds 10MB"
            )

        covers_dir = Path(settings.UPLOAD_DIR) / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        extension = ALLOWED_COVER_TYPES[file.content_type]
        filename = f"game_{game_id}_{uuid4().hex}{extension}"
        cover_path = covers_dir / filename

        with open(cover_path, "wb") as cover_file:
            cover_file.write(contents)

        old_cover_url = game_row["cover_url"]
        cover_url = f"/covers/{filename}"
        cursor.execute(
            """
            UPDATE games
            SET cover_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (cover_url, game_id)
        )
        conn.commit()
        cursor.execute(select_game_sql("WHERE g.id = ?"), (game_id,))
        row = cursor.fetchone()
        conn.close()

        if old_cover_url and old_cover_url.startswith("/covers/"):
            old_path = covers_dir / os.path.basename(old_cover_url)
            if old_path.exists():
                old_path.unlink()

        return game_response(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading game cover: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading game cover"
        )


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game(game_id: int):
    """Delete a board game and all associated data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if game exists
        cursor.execute(select_game_sql("WHERE g.id = ?"), (game_id,))
        game_row = cursor.fetchone()
        if not game_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        # Delete from database (cascading deletes will handle related records)
        cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
        conn.commit()
        conn.close()

        if game_row["cover_url"] and game_row["cover_url"].startswith("/covers/"):
            cover_path = Path(settings.UPLOAD_DIR) / "covers" / os.path.basename(game_row["cover_url"])
            if cover_path.exists():
                cover_path.unlink()
        
        # Delete vector store collection
        vector_store.delete_collection(game_id)
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting game: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting game"
        )
