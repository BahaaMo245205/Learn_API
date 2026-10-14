from fastapi import FastAPI ,HTTPException,status
from Notifications.Database.db import *
from Notifications.Models.main import  *
from Notifications.Core.security import *

app = FastAPI()

# 1. جلب كل إشعاراتي
@app.get("/notifications", response_model=list[NotificationResponse])
def get_my_notifications(
    db: Session = Depends(get_db),
    # current_user: dict = Depends(get_current_user)   # فعّلها لما يبقى عندك Auth
    user_id: str = "USER_ID_HERE"  # مؤقتًا للتجربة
):
    result = db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


# 2. الإشعارات اللي لسه مقريتهاش
@app.get("/notifications/unread", response_model=list[NotificationResponse])
def get_unread_notifications(
    db: Session = Depends(get_db),
    user_id: str = "USER_ID_HERE"
):
    result = db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False
        )
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


# 3. تعليم إشعار كمقروء
@app.put("/notifications/{notification_id}/read")
def mark_as_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user_id: str = "USER_ID_HERE"
):
    notification = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
    ).scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()
    return {"message": "Marked as read"}


# 4. تعليم الكل كمقروء
@app.put("/notifications/read-all")
def mark_all_as_read(
    db: Session = Depends(get_db),
    user_id: str = "USER_ID_HERE"
):
    result = db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False
        )
    )
    notifications = result.scalars().all()

    for n in notifications:
        n.is_read = True

    db.commit()
    return {"message": f"Marked {len(notifications)} notifications as read"}


# 5. إنشاء إشعار (عادة بيتنادى من جوه السيرفر مش من الفرونت)
@app.post("/notifications", status_code=status.HTTP_201_CREATED)
def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db)
):
    notification = Notification(
        user_id=data.user_id,
        title=data.title,
        message=data.message,
        type=data.type,
        data=data.data,
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification