"""Pydantic request/response schemas with validation."""
import datetime as dt

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---- Auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.isalpha() or v.isdigit():
            raise ValueError("Password must mix letters and numbers.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


# ---- Chat ----
class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=16000)


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=16000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    web: bool = False  # opt-in internet access for this message


class ConversationOut(BaseModel):
    id: str
    title: str
    updated_at: dt.datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: dt.datetime

    class Config:
        from_attributes = True
