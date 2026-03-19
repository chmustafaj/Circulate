from fastapi import APIRouter

from circulate_backend.domain.event_log_service import append_event
from circulate_backend.domain.events import DomainEvent

router = APIRouter(prefix="/events", tags=["events"])


@router.post("")
def create_event(event: DomainEvent) -> dict:
    created = append_event(event, publish=True)
    return {"event_id": str(created.event_id)}

