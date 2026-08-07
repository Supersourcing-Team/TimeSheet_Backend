from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.modules.auth.schema import (
    GoogleLoginRequest,
    RefreshTokenRequest,
    UserAuthResponse,
)
from app.modules.auth.service import login_with_google, refresh_access_token

router = APIRouter()


@router.post("/google/login", summary="Login using Google SSO")
async def google_login(request: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a Google ID Token for JWT access and refresh tokens.
    User must already be registered in the database by an Admin.
    """
    auth_data = await login_with_google(request.credential, db)
    return success_response(
        data=auth_data.model_dump(),
        message="Login successful",
    )


@router.post("/refresh", summary="Refresh access token")
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchanges a valid refresh token for a new access token and refresh token.
    """
    auth_data = await refresh_access_token(request.refresh_token, db)
    return success_response(
        data=auth_data.model_dump(),
        message="Token refreshed successfully",
    )


@router.post("/logout", summary="Logout user")
async def logout():
    """
    Stateless logout: Instructs the client to discard their tokens.
    """
    return success_response(
        data=None,
        message="Successfully logged out. Please discard your tokens locally.",
    )


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

