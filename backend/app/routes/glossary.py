"""Routes for rulebook glossary terms."""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List
import logging

from app.database import get_db_connection
from app.models import GlossaryTermResponse, GlossaryTermUpdate
from app.services.glossary_service import GlossaryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{game_id}", response_model=List[GlossaryTermResponse])
async def list_glossary_terms(
    game_id: int,
    enabled_only: bool = True,
    limit: int = Query(80, ge=1, le=200),
):
    """List game glossary terms."""
    try:
        _ensure_game(game_id)
        return [
            GlossaryTermResponse(**term)
            for term in GlossaryService.list_terms(game_id, enabled_only=enabled_only, limit=limit)
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing glossary terms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing glossary terms",
        )


@router.post("/{game_id}/regenerate", response_model=List[GlossaryTermResponse])
async def regenerate_glossary(game_id: int):
    """Regenerate glossary terms from the current processed chunks."""
    try:
        _ensure_game(game_id)
        terms = GlossaryService.regenerate_for_game(game_id)
        return [GlossaryTermResponse(**term) for term in terms]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating glossary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error regenerating glossary: {str(e)}",
        )


@router.put("/terms/{term_id}", response_model=GlossaryTermResponse)
async def update_glossary_term(term_id: int, payload: GlossaryTermUpdate):
    """Update one glossary term after admin review."""
    try:
        updated = GlossaryService.update_term(term_id, payload.model_dump())
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Glossary term not found",
            )
        return GlossaryTermResponse(**updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating glossary term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating glossary term",
        )


def _ensure_game(game_id: int) -> None:
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )
