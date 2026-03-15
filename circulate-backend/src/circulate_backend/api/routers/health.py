from fastapi import APIRouter

from circulate_backend.domain.health_service import get_health

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return get_health()

