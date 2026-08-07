from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.schema import GoogleLoginRequest, TokenResponse, RefreshTokenRequest
from app.modules.auth.service import login_with_google, refresh_access_token

router = APIRouter()

@router.post("/google/login", response_model=TokenResponse, summary="Login using Google SSO")
async def google_login(request: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a Google ID Token for JWT access and refresh tokens.
    User must already be registered in the database by an Admin.
    """
    return await login_with_google(request.credential, db)


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a valid refresh token for a new access token and refresh token.
    """
    return await refresh_access_token(request.refresh_token, db)


@router.post("/logout", summary="Logout user")
async def logout():
    """
    Stateless logout: Instructs the client to discard their tokens.
    If server-side token invalidation is required, implement a blacklist mechanism here.
    """
    return {"success": True, "message": "Successfully logged out. Please discard your tokens locally."}
