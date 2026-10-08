import re

from pydantic import BaseModel, Field, field_validator


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        v = v.strip().title()
        if not re.match(r"^[A-Za-z0-9_]+$", v):
            raise ValueError(
                "Username must contain only letters, numbers and underscore"
            )
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class PostCreate(BaseModel):
    title: str
    content: str


class Comments(BaseModel):
    text: str


class PostResponse(BaseModel):
    id:str
    title: str
    content: str
    author: str
    created_at: str
