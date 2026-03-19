from __future__ import annotations

import json
from typing import Optional

import structlog

from circulate_backend.domain.events import DomainEvent
from circulate_backend.infra.db import get_sessionmaker
from circulate_backend.infra.db_models import EventLog
from circulate_backend.infra.redis_client import get_redis_client

log = structlog.get_logger(__name__)


def append_event(event: DomainEvent, publish: bool = True) -> DomainEvent:
    session_factory = get_sessionmaker()
    with session_factory() as session:
        row = EventLog(
            id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
        )
        session.add(row)
        session.commit()

    published_to: Optional[str] = None
    if publish:
        r = get_redis_client()
        if r is not None:
            channel = r.channel
            r.client.publish(channel, json.dumps(event.model_dump(mode="json")))
            published_to = channel

    log.info(
        "event_log.appended",
        event_id=str(event.event_id),
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        published_to=published_to,
    )
    return event

