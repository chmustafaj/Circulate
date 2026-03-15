from fastapi import FastAPI
from dotenv import load_dotenv

from circulate_backend.api.routers.health import router as health_router
from circulate_backend.infra.logging import configure_logging
from circulate_backend.infra.request_id import RequestIdMiddleware


def create_app() -> FastAPI:
    load_dotenv()
    configure_logging()

    app = FastAPI(title="Circulate Backend")
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health_router)
    return app


app = create_app()

