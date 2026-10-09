from fastapi import (
    FastAPI,
    Depends,
    status,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Query,
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
    UniqueConstraint,
)
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase, relationship
from .Models import *
from .helper import *
import json
import uuid

app = FastAPI()
PATH_DB = "sqlite:///./chat.db"

engine = create_engine(PATH_DB)
LocalSession = sessionmaker(bind=engine)
active_connections: Dict[int, List[WebSocket]] = {}


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="member")
    is_active = Column(Boolean, default=False, nullable=False)

    participations = relationship(
        "Participant", back_populates="user", cascade="all, delete-orphan"
    )
    messages = relationship("Message", back_populates="sender")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    is_group = Column(Boolean, default=False)
    name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    participants = relationship(
        "Participant", back_populates="conversation", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Participant(Base):
    __tablename__ = "participants"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    conversation_id = Column(
        String(32), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String(20), nullable=False, default="member")
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)

    # ?
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="_user_conversation_uc"),
    )

    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User", back_populates="participations")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    conversation_id = Column(
        String(32), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id = Column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content = Column(Text, nullable=False)
    type = Column(String(20), default="text")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="messages")


def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
GetDB = Depends(get_db)
GetCurrentUser = Depends(get_current_user)


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


@app.get("/api/auth/GetAllUsers", status_code=status.HTTP_200_OK)
async def Get_all_users(session: Session = GetDB, current_user: dict = GetCurrentUser):
    result = session.execute(select(User).where(User.id == current_user.get("id")))
    get_role_user = result.scalar_one_or_none()

    if not get_role_user or get_role_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="عذراً، هذه الصلاحية مخصصة لمدير النظام فقط!",
        )

    result = session.execute(select(User))
    GetAllUsers = result.scalars().all()
    if GetAllUsers:return GetAllUsers


@app.patch("/api/auth/activation/{id}", status_code=status.HTTP_200_OK)
async def activate_user(
    id: str, session: Session = GetDB, current_user: dict = GetCurrentUser
):
    result = session.execute(select(User).where(User.id == current_user.get("id")))
    get_role_user = result.scalar_one_or_none()

    if not get_role_user or get_role_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="عذراً، هذه الصلاحية مخصصة لمدير النظام فقط!",
        )

    result = session.execute(select(User).where(User.id == id))
    active_user = result.scalar_one_or_none()

    if not active_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="المستخدم المراد تفعيله غير موجود!",
        )

    active_user.is_active = True

    await session.commit()
    await session.refresh(active_user)

    return {
        "message": "Update successfully",
        "user_name": active_user.username,
        "id": active_user.id,
        "is_active": active_user.is_active,
    }


@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket, conversation_id: int, token: str = Query(...)
):
    await websocket.accept()
    user_id = get_current_user(token=token)
    print(f"User {user_id} connected to conversation {conversation_id}")

    if conversation_id not in active_connections:
        active_connections[conversation_id] = []
    active_connections[conversation_id].append(websocket)

    try:
        while True:
            raw_data = await websocket.receive_text()

            if not raw_data or raw_data.strip() == "":
                continue

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            content = data.get("content", "")

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
        print(f"User {user_id} disconnected from conversation {conversation_id}")

    finally:
        if conversation_id in active_connections:
            if websocket in active_connections[conversation_id]:
                active_connections[conversation_id].remove(websocket)

            if not active_connections[conversation_id]:
                del active_connections[conversation_id]
