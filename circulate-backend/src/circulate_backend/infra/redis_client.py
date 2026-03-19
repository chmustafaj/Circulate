import os
from dataclasses import dataclass
from typing import Optional

import redis
import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RedisClient:
    client: redis.Redis
    channel: str


def get_redis_client() -> Optional[RedisClient]:
    url = os.getenv("REDIS_URL")
    if not url:
        return None

    channel = os.getenv("REDIS_EVENTS_CHANNEL", "domain_events")
    try:
        client = redis.from_url(url, decode_responses=True)
        client.ping()
        return RedisClient(client=client, channel=channel)
    except Exception as e:
        log.warning("redis.unavailable", error=str(e))
        return None

