from fastapi import FastAPI, HTTPException, status
from Notifications.Database.db import *
from Notifications.Models.main import *
from Notifications.Core.security import *
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"],
    allow_credentials=True,
)


@app.get("/notifications", response_model=list[NotificationResponse])
def get_my_notifications(db: Session = Depends(get_db), user_id: str = "USER_ID_HERE"):
    result = db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


@app.get("/notifications/unread-count")
def get_unread_notifications(
    db: Session = Depends(get_db), user_id: str = "USER_ID_HERE"
):
    result = db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .order_by(Notification.created_at.desc())
    )
    return result.scalar()


@app.put("/notifications/{notification_id}/read")
def mark_as_read(
    notification_id: str, db: Session = Depends(get_db), user_id: str = "USER_ID_HERE"
):
    notification = db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    ).scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()
    return {"message": "Marked as read"}


@app.put("/notifications/read-all")
def mark_all_as_read(db: Session = Depends(get_db), user_id: str = "USER_ID_HERE"):
    result = db.execute(
        select(Notification).where(
            Notification.user_id == user_id, Notification.is_read == False
        )
    )
    notifications = result.scalars().all()

    for n in notifications:
        n.is_read = True

    db.commit()
    return {"message": f"Marked {len(notifications)} notifications as read"}


@app.post("/notifications", status_code=status.HTTP_201_CREATED)
def create_notification(data: NotificationCreate, db: Session = Depends(get_db)):
    notification = Notification(
        user_id=data.user_id,
        title=data.title,
        message=data.message,
        type=data.type,
        data=data.data,
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


@app.delete("/notifications/delete/{NotificationId}")
async def delete_notification(NotificationId: str, db: Session = Depends(get_db)):
    result = db.execute(select(Notification).where(Notification.id == NotificationId))
    get_notification = result.scalar_one_or_none()

    if get_notification:
        db.delete(get_notification)
        db.commit()
