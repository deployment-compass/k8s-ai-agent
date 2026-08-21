from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.chat import router as chat_router
from app.api.v1.kubernetes import router as kubernetes_router
from app.config import settings
from app.kubernetes.config import load_kubernetes_config
from app.logging_setup import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings)
    load_kubernetes_config()
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.include_router(chat_router, prefix="/api/v1")
app.include_router(kubernetes_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
