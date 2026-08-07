from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from jose import jwt, JWTError

from app.models.user import User
from app.modules.auth.oauth import verify_google_token
from app.modules.auth.jwt import create_access_token, create_refresh_token, verify_token
from app.modules.auth.schema import TokenResponse
from app.core.config import settings

async def login_with_google(credential: str, db: AsyncSession) -> TokenResponse:
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
        
    # 2. Check if user exists in DB and is Active
    result = await db.execute(
        select(User).options(selectinload(User.role)).filter(User.email == email)
    )
    user = result.scalar_one_or_none()
    
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
        "employee_id": user.employee_id
    }
    user_id_for_refresh = str(user.id)
    
    access_token = create_access_token(data=payload)
    refresh_token = create_refresh_token(data={"sub": user_id_for_refresh})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

async def refresh_access_token(refresh_token: str, db: AsyncSession) -> TokenResponse:
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
        
    user_id = int(user_id_str)
    result = await db.execute(
        select(User).options(selectinload(User.role)).filter(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or user.status != "Active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
        
    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.name,
        "employee_id": user.employee_id
    }
    
    new_access_token = create_access_token(data=token_payload)
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )
