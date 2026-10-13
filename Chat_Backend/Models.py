from pydantic import BaseModel, EmailStr
from datetime import datetime


class Register(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr


class Login(BaseModel):
    email: EmailStr
    password: str


class ActiveUser(BaseModel):
    UserId: str
    is_active: bool


class CreateConversationRequest(BaseModel):
    name: str = None
    is_group: bool = False
    recipient_id: str = None


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    sender: str
    content: str
    created_at: datetime
