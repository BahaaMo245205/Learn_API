import random
import string
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import Column, String, create_engine, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

app = FastAPI()
Base = declarative_base()

URL_DB = "sqlite:///./url.db"
engine = create_engine(URL_DB)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_short_code(width: int = 6) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=width))


class URLCreate(BaseModel):
    original_url: str


class UrlShort(Base):
    __tablename__ = "Url"

    id = Column(
        "id",
        String,
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    url = Column("url", String, nullable=False, unique=True)
    short = Column("short", String, nullable=False, unique=True)


Base.metadata.create_all(bind=engine)

GetDB = Depends(get_db)


@app.get("/hello")
async def hello():
    return {"Massage": "Hello World"}


@app.post("/shorten")
async def create_short_url(payload: URLCreate, session: Session = GetDB):
    short_code = generate_short_code()
    while session.execute(
        select(UrlShort).where(UrlShort.short == short_code)
    ).scalar_one_or_none():
        short_code = generate_short_code()

    try:
        add_url = UrlShort(url=payload.original_url, short=short_code)
        session.add(add_url)
        session.commit()
        session.refresh(add_url)
        return {
            "message": "Added URL successfully.",
            "short_code": add_url.short,
            "short_url": f"http://localhost:8000/{add_url.short}",
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error: {e}"
        )


@app.get("/{short_code}")
async def redirect_to_original(short_code: str, session: Session = Depends(get_db)):
    query = session.execute(select(UrlShort).where(UrlShort.short == short_code))
    get_urls = query.scalar_one_or_none()

    if get_urls:
        return RedirectResponse(url=get_urls.url)
    else:
        raise HTTPException(status_code=404, detail="URL not found")
