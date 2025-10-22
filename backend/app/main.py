from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import create_api_router
from .config import settings
from .db import Base, engine
from . import models  # noqa: F401
from .services.chaos import ChaosMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Chaos-Effect", "X-Chaos-Delay", "X-Chaos-Stale", "X-Chaos-State"],
    )
    app.add_middleware(
        ChaosMiddleware,
        service_name="backend",
        exclude_paths=("/api/v1/chaos", "/docs", "/openapi.json"),
    )
    Base.metadata.create_all(bind=engine)
    app.include_router(create_api_router())
    return app


app = create_app()
