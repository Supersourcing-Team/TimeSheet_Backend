from pydantic import BaseModel
from typing import Optional

class GoogleLoginRequest(BaseModel):
    credential: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenPayload(BaseModel):
    sub: str
    email: str
    role: str
    employee_id: str
    exp: Optional[int] = None
    iat: Optional[int] = None
