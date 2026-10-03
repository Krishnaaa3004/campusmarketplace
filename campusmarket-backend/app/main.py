from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes.auth import router as auth_router
from app.api.routes.listings import router as listings_router
from app.api.routes.requests import router as requests_router
from app.core.config import settings
from app.db.session import engine

app = FastAPI(title=settings.APP_NAME)

app.include_router(auth_router)
app.include_router(listings_router)
app.include_router(requests_router)

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"  # must match routes/listings.py
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Confirms the API is up and can actually reach the Supabase database."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "environment": settings.ENVIRONMENT}
