from fastapi import (
    FastAPI,
    Depends,
    status,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Query,
)

from fastapi.responses import RedirectResponse

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
    func,
    and_,
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
    email = user.email
    password = user.password
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
    "/api/auth/login",  status_code=status.HTTP_200_OK
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
    if not get_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="تأكد من الادمن عن تفعيل حسابك !",
        )

    if not verify_password(password, get_user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="تأكيد من الباسرود او الايميل")

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
    if GetAllUsers:
        return GetAllUsers


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

    session.commit()
    session.refresh(active_user)

    return {
        "message": "Update successfully",
        "user_name": active_user.username,
        "id": active_user.id,
        "is_active": active_user.is_active,
    }


@app.post("/api/conversations/create", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: CreateConversationRequest,
    session: Session = GetDB,
    current_user: dict = GetCurrentUser,
):
    current_user_id = current_user.get("id")

    if not current_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if data.is_group:
        if not data.name or not data.name.strip():
            raise HTTPException(
                status_code=400, detail="Group name is required when is_group=True"
            )
    else:
        if not data.recipient_id:
            raise HTTPException(
                status_code=400,
                detail="recipient_id is required for one-to-one conversation",
            )
        if data.recipient_id == current_user_id:
            raise HTTPException(
                status_code=400, detail="Cannot create conversation with yourself"
            )

    if not data.is_group and data.recipient_id:
        existing = (
            session.query(Conversation)
            .join(Participant, Participant.conversation_id == Conversation.id)
            .filter(
                Conversation.is_group == False,
                Participant.user_id.in_([current_user_id, data.recipient_id]),
            )
            .group_by(Conversation.id)
            .having(func.count(Participant.user_id) == 2)
            .first()
        )

        user_conversations = (
            session.query(Participant.conversation_id)
            .join(Conversation)
            .filter(
                Participant.user_id == current_user_id, Conversation.is_group == False
            )
            .all()
        )
        user_conv_ids = [c[0] for c in user_conversations]

        if user_conv_ids:
            existing = (
                session.query(Participant)
                .filter(
                    Participant.conversation_id.in_(user_conv_ids),
                    Participant.user_id == data.recipient_id,
                )
                .first()
            )
            if existing:
                conversation = session.query(Conversation).get(existing.conversation_id)
                return {
                    "message": "Conversation already exists",
                    "conversation_id": conversation.id,
                    "is_group": conversation.is_group,
                    "name": conversation.name,
                }

    new_conversation = Conversation(
        is_group=data.is_group, name=data.name if data.is_group else None
    )
    session.add(new_conversation)
    session.flush()

    participants = [current_user_id]
    if data.recipient_id:
        participants.append(data.recipient_id)

    participants = list(set(participants))
    for user_id in participants:
        participant = Participant(conversation_id=new_conversation.id, user_id=user_id)
        session.add(participant)

    session.commit()
    session.refresh(new_conversation)

    return {
        "message": "Conversation created successfully",
        "conversation_id": new_conversation.id,
        "is_group": new_conversation.is_group,
        "name": new_conversation.name,
        "participants": participants,
    }


@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(...),
):
    try:
        current_user = decode_jwt(token=token)
        user_id = current_user.get("id")
        if not user_id:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    session: Session = next(get_db())

    try:
        result = session.execute(select(User).where(User.id == user_id))
        get_user = result.scalar_one_or_none()

        if not get_user or not get_user.role:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        participant_result = session.execute(
            select(Participant).where(
                Participant.conversation_id == conversation_id,
                Participant.user_id == user_id,
            )
        )
        participant = participant_result.scalar_one_or_none()

        if not participant:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        print(f"✅ User {user_id} connected to conversation {conversation_id}")

        if conversation_id not in active_connections:
            active_connections[conversation_id] = []
        active_connections[conversation_id].append(websocket)

        try:
            while True:
                raw_data = await websocket.receive_text()
                if not raw_data or raw_data.strip() == "":
                    continue

                # try:
                #     data = json.loads(raw_data)
                # except json.JSONDecodeError:
                #     await websocket.send_json({"error": "Invalid JSON"})
                #     continue

                # content = data.get("content", "").strip()
                # if not content:
                #     continue

                new_message = Message(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    content=raw_data,
                    type="text",
                )
                session.add(new_message)
                session.commit()
                session.refresh(new_message)

                message_payload = {
                    "id": new_message.id,
                    "sender_id": user_id,
                    "content": raw_data,
                    "conversation_id": conversation_id,
                    "created_at": (
                        new_message.created_at.isoformat()
                        if new_message.created_at
                        else None
                    ),
                }

                connections = active_connections.get(conversation_id, []).copy()
                for connection in connections:
                    try:
                        await connection.send_json(message_payload)
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

        session.close()