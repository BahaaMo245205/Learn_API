import hashlib
import os
import re
import uuid
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator

load_dotenv()

# ==================== Config ====================
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing in .env")

# ==================== Security ====================
security = HTTPBearer()

app = FastAPI(title="Auth API", version="1.0.0")

users_db: list[dict] = []


# ==================== Helpers ====================
def hash_password(password: str) -> str:
    convert_hash_password = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return convert_hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    check_password_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    if check_password_hash == hashed_password:
        return True
    return False


def is_password_strong(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        user_id: str = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"id": user_id, "username": username}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== Schemas ====================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        v = v.strip().title()
        if not re.match(r"^[A-Za-z0-9_]+$", v):
            raise ValueError(
                "Username must contain only letters, numbers and underscore"
            )
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


# ==================== Routes ====================
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserRegister):
    if user.password != user.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and confirm password do not match",
        )

    if not is_password_strong(user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too weak. Must contain: uppercase, lowercase, number, special character, and at least 8 characters",
        )

    for existing in users_db:
        if existing["username"].lower() == user.username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )

    new_user = {
        "id": str(uuid.uuid4()),
        "username": user.username,
        "hashed_password": hash_password(user.password),
    }
    users_db.append(new_user)

    return {
        "message": "User registered successfully",
        "id": new_user["id"],
        "username": new_user["username"],
    }


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(user: UserLogin):
    db_user = None
    for u in users_db:
        if u["username"].lower() == user.username.strip().title().lower():
            db_user = u
            break

    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"username": db_user["username"], "id": db_user["id"]}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user["id"],
        "username": db_user["username"],
    }


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "message": f"Hello {current_user['username']}, you are authenticated!",
    }


@app.get("/api/auth/check")
async def check_token(current_user: dict = Depends(get_current_user)):
    return {"valid": True, "user": current_user}
