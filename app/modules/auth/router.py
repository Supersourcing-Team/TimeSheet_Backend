import os
from fastapi import APIRouter, Depends, Response, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.modules.users.model import User
from app.modules.auth.schema import (
    GoogleLoginRequest,
    UserAuthResponse,
)
from app.modules.auth.service import login_with_google, refresh_access_token
from app.core.config import settings

router = APIRouter()

# In production (Vercel → Render cross-site), cookies MUST be Secure + SameSite=None.
# Locally (same-origin via Vite proxy) SameSite=lax works without HTTPS.
_IS_PRODUCTION = settings.ENVIRONMENT == "production"
_COOKIE_SAMESITE = "none" if _IS_PRODUCTION else "lax"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=_IS_PRODUCTION,
        samesite=_COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_IS_PRODUCTION,
        samesite=_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=_IS_PRODUCTION,
        samesite=_COOKIE_SAMESITE,
        path="/",
    )
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=_IS_PRODUCTION,
        samesite=_COOKIE_SAMESITE,
        path="/",
    )


@router.post("/google/login", summary="Login using Google SSO")
async def google_login(request: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a Google ID Token for JWT access and refresh tokens.
    User must already be registered in the database by an Admin.
    """
    auth_data = await login_with_google(request.credential, db)
    resp = success_response(
        data={
            "access_token": auth_data.access_token,
            "refresh_token": auth_data.refresh_token,
            "token_type": "bearer",
            "user": auth_data.user.model_dump(),
        },
        message="Login successful",
    )

    set_auth_cookies(resp, auth_data.access_token, auth_data.refresh_token)
    return resp


@router.post("/refresh", summary="Refresh access token")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a valid refresh token for a new access token and refresh token.
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
    auth_data = await refresh_access_token(token, db)
    resp = success_response(
        data={"user": auth_data.user.model_dump()},
        message="Token refreshed successfully",
    )
    set_auth_cookies(resp, auth_data.access_token, auth_data.refresh_token)
    return resp


@router.post("/logout", summary="Logout user")
async def logout():
    """
    Stateless logout: Instructs the client to discard their tokens.
    """
    resp = success_response(
        data=None,
        message="Successfully logged out.",
    )
    clear_auth_cookies(resp)
    return resp


@router.get("/me", summary="Get authenticated user profile")
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Returns profile information for the currently authenticated active user.
    """
    user_response = UserAuthResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role.name,
        employee_id=current_user.employee_id,
    )
    return success_response(
        data=user_response.model_dump(),
        message="User profile retrieved successfully",
    )

