"""
Routes for application settings.
"""

from fastapi import APIRouter, HTTPException, status
import logging

from app.models import ModelConfigResponse, ModelConfigUpdate
from app.services.model_config import get_model_config, save_model_config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/model-config", response_model=ModelConfigResponse)
async def read_model_config():
    """Get model provider configuration."""
    try:
        return get_model_config()
    except Exception as e:
        logger.error(f"Error reading model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reading model config",
        )


@router.put("/model-config", response_model=ModelConfigResponse)
async def update_model_config(config: ModelConfigUpdate):
    """Update model provider configuration."""
    try:
        return save_model_config(config.model_dump())
    except Exception as e:
        logger.error(f"Error updating model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating model config",
        )
