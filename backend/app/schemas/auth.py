from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    is_guest: bool


class GuestResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    guest_id: int
    is_guest: bool = True


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class GuestConvertRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
