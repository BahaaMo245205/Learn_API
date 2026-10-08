from pydantic import  BaseModel, EmailStr
from datetime import datetime

class Register(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password : str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str

class Login(BaseModel):
    email: EmailStr
    password: str


class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: int
    sender: str
    content: str
    created_at: datetime

