from fastapi import FastAPI
from dotenv import load_dotenv

from circulate_backend.api.routers.assets import router as assets_router
from circulate_backend.api.routers.events import router as events_router
from circulate_backend.api.routers.health import router as health_router
from circulate_backend.api.routers.verify import router as verify_router
from circulate_backend.infra.db import create_db_engine
from circulate_backend.infra.db_models import Base
from circulate_backend.infra.logging import configure_logging
from circulate_backend.infra.request_id import RequestIdMiddleware


def create_app() -> FastAPI:
    load_dotenv()
    configure_logging()

    app = FastAPI(title="Circulate Backend")
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health_router)
    app.include_router(events_router)
    app.include_router(assets_router)
    app.include_router(verify_router)

    try:
        engine = create_db_engine()
        Base.metadata.create_all(bind=engine)
    except Exception:
        # DB might not be configured yet (e.g., running without Postgres).
        pass

    return app


app = create_app()

