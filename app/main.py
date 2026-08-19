from fastapi import FastAPI

from app.api.v1.chat import router as chat_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
