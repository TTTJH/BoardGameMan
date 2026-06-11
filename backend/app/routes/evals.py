"""Routes for rulebook evaluation tooling."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from evals.generate_candidate_questions import generate_candidate_questions
from app.services.eval_service import EvalService

logger = logging.getLogger(__name__)
router = APIRouter()


class EvalCaseUpdate(BaseModel):
    enabled: Optional[bool] = None
    failure_type: Optional[str] = Field(None, max_length=50)
    review_notes: Optional[str] = Field(None, max_length=1000)
    expected_pages: Optional[List[int]] = None
    expected_terms: Optional[List[str]] = None


@router.post("/{game_id}/candidate-questions")
async def generate_candidate_questions_route(
    game_id: int,
    max_pages: int = Query(4, ge=1, le=20),
    questions_per_page: int = Query(2, ge=1, le=5),
):
    """Generate candidate retrieval-eval questions for a prepared rulebook."""
    try:
        payload, output_path = generate_candidate_questions(
            game_id=game_id,
            max_pages=max_pages,
            questions_per_page=questions_per_page,
        )
        return {
            "game_id": payload["game_id"],
            "game_name": payload["game_name"],
            "candidate_count": len(payload["candidates"]),
            "output_path": str(output_path),
            "status": payload["status"],
        }
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except SystemExit as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except Exception as error:
        logger.error(f"Error generating candidate eval questions for game {game_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating candidate questions: {error}",
        )


@router.post("/{game_id}/promote-candidates")
async def promote_candidate_questions_route(game_id: int):
    """Promote the latest generated candidate questions into stable eval cases."""
    try:
        return EvalService.promote_candidates(game_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except Exception as error:
        logger.error(f"Error promoting candidate eval questions for game {game_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error promoting candidate questions: {error}",
        )


@router.get("/{game_id}/cases")
async def list_eval_cases_route(game_id: int, enabled_only: bool = False):
    """List stable eval cases for a game."""
    try:
        return EvalService.list_cases(game_id, enabled_only=enabled_only)
    except Exception as error:
        logger.error(f"Error listing eval cases for game {game_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing eval cases",
        )


@router.put("/cases/{case_id}")
async def update_eval_case_route(case_id: str, payload: EvalCaseUpdate):
    """Update review metadata for one stable eval case."""
    try:
        return EvalService.update_case(case_id, payload.model_dump(exclude_unset=True))
    except ValueError as error:
        message = str(error)
        code = status.HTTP_404_NOT_FOUND if "not found" in message.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=message)
    except Exception as error:
        logger.error(f"Error updating eval case {case_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating eval case",
        )


@router.post("/{game_id}/run")
async def run_eval_route(game_id: int, top_k: int = Query(8, ge=1, le=30)):
    """Run stable retrieval evaluation for a prepared rulebook."""
    try:
        return EvalService.run(game_id, top_k=top_k)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except Exception as error:
        logger.error(f"Error running eval for game {game_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running eval: {error}",
        )


@router.post("/{game_id}/run-chat")
async def run_chat_eval_route(
    game_id: int,
    top_k: int = Query(8, ge=1, le=30),
    max_cases: int = Query(10, ge=1, le=50),
):
    """Run chat-answer evaluation for enabled stable cases."""
    try:
        return EvalService.run_chat(game_id, top_k=top_k, max_cases=max_cases)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except Exception as error:
        logger.error(f"Error running chat eval for game {game_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running chat eval: {error}",
        )


@router.get("/{game_id}/latest-run")
async def latest_eval_run_route(game_id: int, mode: Optional[str] = None):
    """Return the latest stable eval run for a game."""
    try:
        latest = EvalService.latest_run(game_id, mode=mode)
        if not latest:
            return {"available": False, "summary": "No stable eval set has been run for this game yet."}
        return latest
    except Exception as error:
        logger.error(f"Error loading latest eval run for game {game_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error loading latest eval run",
        )


@router.get("/{game_id}/failure-analysis")
async def failure_analysis_route(game_id: int, mode: Optional[str] = "retrieval"):
    """Summarize failure clusters for the latest eval run."""
    try:
        return EvalService.failure_analysis(game_id, mode=mode)
    except Exception as error:
        logger.error(f"Error loading failure analysis for game {game_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error loading failure analysis",
        )
