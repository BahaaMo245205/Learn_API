from fastapi import (
    FastAPI,
    Depends,
    status,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)

from typing import Dict, List

from sqlalchemy import (
    create_engine,
    Column,
    String,
    ForeignKey,
    Integer,
    Boolean,
    DateTime,
    Text,
    select,
)
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from .Models import *
from .helper import *
import json

app = FastAPI()
PATH_DB = "sqlite:///./chat.db"

engine = create_engine(PATH_DB)
LocalSession = sessionmaker(bind=engine)
active_connections: Dict[int, List[WebSocket]] = {}


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "User"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)


class Conversation(Base):
    __tablename__ = "Conversation"

    id = Column(Integer, primary_key=True)
    is_group = Column(Boolean, default=False)  # False = one-to-one
    name = Column(String, nullable=True)  # اسم الجروب فقط
    created_at = Column(DateTime)


class Participant(Base):
    __tablename__ = "Participant"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("Conversation.id"))
    user_id = Column(Integer, ForeignKey("User.id"))
    joined_at = Column(DateTime)


class Message(Base):
    __tablename__ = "Message"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("Conversation.id"))
    sender_id = Column(Integer, ForeignKey("User.id"))
    content = Column(Text)
    created_at = Column(DateTime)


def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
GetDB = Depends(get_db)


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user: Register, session: Session = GetDB):
    username = user.username
    password = user.password
    email = user.email
    confirm_password = user.confirm_password

    if not username and not password and not confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="البيانات مفهومة لكن منطقًا غلط",
        )

    if password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="الرجاء تأكيد من الباسورد",
        )

    if not is_password_strong(password=password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="نريد الباسرود تكون قوي",
        )

    convert_hash = hash_password(password=password)

    add_user = User(username=username, email=email, password=convert_hash)
    try:
        session.add(add_user)
        session.commit()
        return {"Massage": "Added successfuly user", "status": "success"}
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"خطأ : {e}"
        )


@app.post(
    "/api/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK
)
async def login(user: Login, session: Session = GetDB):
    email = user.email
    password = user.password

    if not email and not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="البيانات مفهومة لكن منطقًا غلط",
        )

    query_result = session.execute(select(User).where(User.email == email))

    get_user = query_result.scalar_one_or_none()

    if not get_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="تأكيد من الباسرود او الايميل",
        )

    if verify_password(password, get_user.password):

        access_token = create_access_token(
            {
                "id": str(get_user.id),
                "username": get_user.email,
            }
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": str(get_user.id),
            "email": get_user.email,
        }


"""
✅ User 5 connected to conversation 1
active_connections : {1: [<starlette.websockets.WebSocket object at 0x00000264805BDF90>]}
raw_data :{
  "content": "مرحبا",
  "sender_id": 5
}
data : {'content': 'مرحبا', 'sender_id': 5}
📩 Message from 5: مرحبا
❌ User 5 disconnected from conversation 1
"""


@app.websocket("/ws/{conversation_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: int, user_id: int):
    await websocket.accept()
    print(f"✅ User {user_id} connected to conversation {conversation_id}")

    if conversation_id not in active_connections:
        active_connections[conversation_id] = []
    active_connections[conversation_id].append(websocket)
    print("active_connections : {}".format(active_connections))

    try:
        while True:
            raw_data = await websocket.receive_text()
            print("raw_data :" + raw_data)

            if not raw_data or raw_data.strip() == "":
                continue

            try:
                data = json.loads(raw_data)
                print("data : {}".format(data))
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            content = data.get("content", "")
            print(f"📩 Message from {user_id}: {content}")

            connections = active_connections.get(conversation_id, []).copy()

            for connection in connections:
                try:
                    await connection.send_json(
                        {
                            "sender_id": user_id,
                            "content": content,
                            "conversation_id": conversation_id,
                        }
                    )
                except Exception:
                    if connection in active_connections.get(conversation_id, []):
                        active_connections[conversation_id].remove(connection)

    except WebSocketDisconnect:
        print(f"❌ User {user_id} disconnected from conversation {conversation_id}")

    finally:
        if conversation_id in active_connections:
            if websocket in active_connections[conversation_id]:
                active_connections[conversation_id].remove(websocket)

            if not active_connections[conversation_id]:
                del active_connections[conversation_id]
