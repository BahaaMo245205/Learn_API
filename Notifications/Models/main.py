from pydantic import BaseModel, EmailStr
from typing import Optional
import datetime



class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str
    data: Optional[str] = None


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime.datetime
    data: Optional[str] = None

    class Config:
        from_attributes = True