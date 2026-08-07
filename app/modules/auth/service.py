from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.oauth import verify_google_token
from app.modules.auth.jwt import create_access_token, create_refresh_token, verify_token
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schema import AuthData, UserAuthResponse


async def login_with_google(credential: str, db: AsyncSession) -> AuthData:
    # 1. Verify Google Token
    idinfo = verify_google_token(credential)
    if not idinfo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = idinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found in token",
        )

    # 2. Check if user exists in DB via Repository
    user = await AuthRepository.get_user_by_email(db, email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not registered. Please contact Admin.",
        )

    if user.status != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    # 3. Generate tokens
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.name,
        "employee_id": user.employee_id,
    }

    access_token = create_access_token(data=payload)
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    user_response = UserAuthResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.name,
        employee_id=user.employee_id,
    )

    return AuthData(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_response,
    )


async def refresh_access_token(refresh_token: str, db: AsyncSession) -> AuthData:
    payload = verify_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    user = await AuthRepository.get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.status != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.name,
        "employee_id": user.employee_id,
    }

    new_access_token = create_access_token(data=token_payload)
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    user_response = UserAuthResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.name,
        employee_id=user.employee_id,
    )

    return AuthData(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=user_response,
    )

