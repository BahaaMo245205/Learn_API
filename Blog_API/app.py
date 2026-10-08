import datetime
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    String,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from Blog_API.helper import (
    create_access_token,
    get_current_user,
    hash_password,
    is_password_strong,
    verify_password,
)
from Blog_API.schemas import (
    Comments,
    PostCreate,
    PostResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
)



app = FastAPI()
URL_DB = "sqlite:///./posts.db"


engine = create_engine(URL_DB, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "User"

    id = Column(
        "id",
        String,
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4().hex),
    )
    username = Column("username", String, nullable=False)
    password = Column("password", String, nullable=False)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")

    comments = relationship(
        "Comment", back_populates="user", cascade="all, delete-orphan"
    )


class Post(Base):
    __tablename__ = "Post"

    id = Column(
        "id",
        String,
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4().hex),
    )
    title = Column("title", String, nullable=False)
    content = Column("content", String, nullable=False)

    author_id = Column("author_id", String, ForeignKey("User.id"), nullable=False)

    create_at = Column(
        "create_at", Date, nullable=False, default=datetime.datetime.utcnow
    )
    update_at = Column(
        "update_at",
        Date,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    is_published = Column("is_published", Boolean, nullable=False, default=True)

    author = relationship("User", back_populates="posts")

    comments = relationship(
        "Comment", back_populates="post", cascade="all, delete-orphan"
    )


class Comment(Base):
    __tablename__ = "Comment"

    id = Column(
        "id",
        String,
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4().hex),
    )

    post_id = Column("post_id", String, ForeignKey("Post.id"), nullable=False)
    user_id = Column("user_id", String, ForeignKey("User.id"), nullable=False)
    content = Column("content", String, nullable=False)

    create_at = Column(
        "create_at", Date, nullable=False, default=datetime.datetime.utcnow
    )

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)

GetDB = Depends(get_db)


# --------- Routes ----------


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserRegister, session: Session = GetDB):
    username = user.username
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

    add_user = User(username=username, password=convert_hash)
    try:
        session.add(add_user)
        session.commit()
        return {"Massage": "Added successfuly user", "status": "success"}
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"خطأ : {e}"
        )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(user: UserLogin, session: Session = GetDB):
    username = user.username
    password = user.password

    if not username and not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="البيانات مفهومة لكن منطقًا غلط",
        )

    queriy = session.execute(select(User).where(User.username == username))

    get_user = queriy.scalar_one_or_none()

    if not get_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="تأكيد من الباسرود او الايميل",
        )

    if verify_password(password, get_user.password):

        access_token = create_access_token(
            {
                "id": get_user.id,
                "username": get_user.username,
            }
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": get_user.id,
            "username": get_user.username,
        }


@app.post("/posts", status_code=status.HTTP_201_CREATED, response_model=PostResponse)
async def create_post(
    post: PostCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = GetDB,
):
    title = post.title
    content = post.content

    if not title and not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="تأكد من البيانات الطلب"
        )

    author_id = current_user.get("id")

    add_post = Post(title=title, content=content, author_id=author_id)
    try:
        session.add(add_post)
        session.commit()
        session.refresh(add_post)
        return PostResponse(
            id=add_post.id, title=title, content=content, author=author_id, created_at=datetime.datetime.now(datetime.UTC).isoformat()
        ).model_dump()
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error : {e}"
        )


@app.get("/posts", status_code=status.HTTP_200_OK)
async def get_all_posts(
    current_user=Depends(get_current_user), session: Session = GetDB
):
    query = session.execute(select(Post))
    get_all_post = query.scalars().all()
    return get_all_post


@app.get("/posts/{post_id}", status_code=status.HTTP_200_OK)
async def get_post(
    post_id: str, current_user=Depends(get_current_user), session: Session = GetDB
):
    query = session.execute(select(Post).where(Post.id == post_id))
    get_post = query.scalar_one_or_none()

    if get_post:
        return {"title": get_post.title, "content": get_post.content}


@app.put("/posts/{post_id}", status_code=status.HTTP_200_OK)
async def update_post(
    post_id: str,
    post: PostCreate,
    current_user=Depends(get_current_user),
    session: Session = GetDB,
):
    query = session.execute(select(Post).where(Post.id == post_id))
    get_post = query.scalar_one_or_none()

    title = post.title
    content = post.content

    if get_post:
        get_post.title = title
        get_post.content = content

        session.commit()

        return {
            "Massage": "Updated successfuly",
            "id": post_id,
        }


@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
    session: Session = GetDB,
):
    query = session.execute(select(Post).where(Post.id == post_id))
    delete_post = query.scalar_one_or_none()

    if delete_post and delete_post.author_id == current_user.get("id"):
        session.delete(delete_post)
        session.commit()

        return {
            "Massage": "Deleted successfuly",
            "id": post_id,
            "title": delete_post.title,
        }


@app.get("/posts/{id}/comments")
async def All_comments(
    id: str, session: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """Get all comments of posts"""
    data: list[dict] = []
    result = session.execute(
        select(Post, Comment)
        .join(Post, Post.id == Comment.post_id)
        .where(Post.id == id)
    )
    rows = result.all()

    if rows:
        for post, comment in rows:
            data.append(
                {
                    "username": comment.user.username,
                    "text": comment.content,
                }
            )
        return {"title": post.title, "content": post.content, "comment": data}


@app.post("/posts/{id}/comments")
async def Add_comments(
    id: str,
    comment: Comments,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    TextOfComment = comment.text
    UserId = current_user.get("id")
    UserName = current_user.get("username")
    PostId = id

    query = session.execute(select(Post).where(Post.id == PostId))
    get_post = query.scalar_one_or_none()
    if get_post:
        add_comment = Comment(post_id=PostId, user_id=UserId, content=TextOfComment)
        session.add(add_comment)
        session.commit()

        return {
            "Massage": f"Added comment at {get_post.title}",
            "User Name": UserName,
            "Text": TextOfComment,
        }


# --------- Routes ----------
