import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, create_engine, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

app = FastAPI(title="Task API", version="1.0.0")

# ==================== Database Setup ====================
Base = declarative_base()

DATABASE_URL = "sqlite:///./Task.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    text = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)


# ==================== Pydantic Schemas ====================
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1)


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    text: str | None = Field(None, min_length=1)


class TaskResponse(BaseModel):
    id: str
    title: str
    text: str

    class Config:
        from_attributes = True 

# ==================== Routes ====================

@app.get("/v1/api/tasks", response_model=list[TaskResponse], status_code=status.HTTP_200_OK)
def get_all_tasks(db: Session = Depends(get_db)):
    tasks = db.execute(select(TaskModel)).scalars().all()
    return tasks


@app.post("/v1/api/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    new_task = TaskModel(title=task.title, text=task.text)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task


@app.put("/v1/api/tasks/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
def update_task(task_id: str, task_update: TaskUpdate, db: Session = Depends(get_db)):
    task = db.execute(select(TaskModel).where(TaskModel.id == task_id)).scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' not found"
        )

    if task_update.title is not None:
        task.title = task_update.title
    if task_update.text is not None:
        task.text = task_update.text

    db.commit()
    db.refresh(task)
    return task


@app.delete("/v1/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.execute(select(TaskModel).where(TaskModel.id == task_id)).scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' not found"
        )

    db.delete(task)
    db.commit()


@app.get("/v1/api/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.execute(select(TaskModel).where(TaskModel.id == task_id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task