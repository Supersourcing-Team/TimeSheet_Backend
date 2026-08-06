from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db

api_router = APIRouter()


@api_router.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint that verifies database connection."""
    try:
        result = await db.execute(text("SELECT 1"))
        db_status = "connected" if result.scalar() == 1 else "unknown"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    return {
        "status": "online",
        "database": db_status,
    }
