from pydantic import BaseModel
from enum import Enum

class RoleEnum(str, Enum):
    ADMIN = "admin"
    CURATOR = "curator"
    STUDENT = "student"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleEnum
    username: str

class RegisterResponse(BaseModel):
    username: str
    role: RoleEnum
    access_token: str
