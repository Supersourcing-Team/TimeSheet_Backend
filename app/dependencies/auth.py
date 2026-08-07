from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.user import User
from app.modules.auth.jwt import verify_token

# This URL is used by Swagger UI to fetch the token. 
# Since we use Google SSO, Swagger UI default flow won't work perfectly without custom JS, 
# but we still use OAuth2PasswordBearer to extract the token from the header for our endpoints.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/google/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
        
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
        
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception
        
    result = await db.execute(
        select(User).options(selectinload(User.role)).filter(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.status != "Active":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
