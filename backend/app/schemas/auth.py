from __future__ import annotations

from datetime import date

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
    full_name: str = Field(min_length=2, max_length=255)
    date_of_birth: date
    address: str = Field(min_length=5, max_length=512)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class GuestConvertRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    date_of_birth: date | None = None
    address: str | None = Field(default=None, min_length=5, max_length=512)
