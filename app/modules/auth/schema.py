from pydantic import BaseModel, ConfigDict
from typing import Optional


class GoogleLoginRequest(BaseModel):
    credential: str


class EmptyRequest(BaseModel):
    pass


class UserAuthResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    employee_id: str

    model_config = ConfigDict(from_attributes=True)


class AuthData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserAuthResponse


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[UserAuthResponse] = None


class TokenPayload(BaseModel):
    sub: str
    email: str
    role: str
    employee_id: str
    exp: Optional[int] = None
    iat: Optional[int] = None

