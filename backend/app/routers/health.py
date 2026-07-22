from fastapi import APIRouter

from app.config import get_settings
from app.indexing.embedding_client import is_embedding_available
from app.schemas.common import success

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    settings = get_settings()
    return success(
        {
            "status": "ok",
            "app": settings.app_name,
            "embedding": {
                "enabled": settings.embedding_enabled,
                "mode": settings.embedding_mode,
                "available": is_embedding_available(),
                "model": settings.embedding_model
                if settings.embedding_mode == "inline"
                else None,
            },
        }
    )
