import os

from celery import Celery


def create_celery() -> Celery:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Celery(
        "circulate_backend",
        broker=redis_url,
        backend=redis_url,
        include=[],
    )


celery_app = create_celery()

