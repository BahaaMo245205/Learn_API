import datetime
import uuid
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.staticfiles import StaticFiles
from PIL import Image
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    or_,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    relationship,
    selectinload,
    sessionmaker,
)

from .models import (
    CategoriesModel,
    ProductsModel,
    UpdateProductsModel,
)

load_dotenv()

app = FastAPI()

SUCCESS = status.HTTP_200_OK
DELETED = status.HTTP_204_NO_CONTENT
CREATED = status.HTTP_201_CREATED
ERROR_SERVER = status.HTTP_500_INTERNAL_SERVER_ERROR
BAD_REQUEST = status.HTTP_400_BAD_REQUEST
PATH_DB = "sqlite:///./Products.db"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "upload"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(UPLOAD_FOLDER)))

engine = create_engine(PATH_DB)
LocalSession = sessionmaker(bind=engine)


class Base(DeclarativeBase): ...


class Categories(Base):
    __tablename__ = "Categories"

    id = Column(
        "id",
        String,
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4().hex),
        unique=True,
    )
    name = Column("name", String, nullable=False)
    description = Column("description", String, nullable=False)

    products = relationship(
        "Products", back_populates="categorie", cascade="all, delete-orphan"
    )


class Products(Base):
    __tablename__ = "Products"

    id = Column(
        "id",
        String,
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4().hex),
        unique=True,
    )
    name = Column("name", String, nullable=False)
    description = Column("description", String, nullable=False)
    price = Column("price", Float, nullable=False)
    quantity = Column("quantity", Integer, nullable=False)
    category_id = Column(
        "category_id",
        String,
        ForeignKey("Categories.id"),
        nullable=False,
    )
    is_active = Column("is_active", Boolean, nullable=False, default=True)
    created_at = Column(
        "created_at", Date, nullable=False, default=datetime.datetime.utcnow
    )

    categories = relationship("Categories", back_populates="products")

    image = relationship(
        "ProductImages",
        back_populates="product",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ProductImages(Base):
    __tablename__ = "ProductImages"
    product_id = Column(
        "product_id",
        String,
        ForeignKey("Products.id"),
        nullable=False,
        unique=True,
        primary_key=True,
    )
    image_url = Column("image_url", String, nullable=False)

    product = relationship("Products", back_populates="image")


def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
GetDB = Depends(get_db)


@app.get("/products", status_code=SUCCESS)
async def GetAllProducts(session: Session = GetDB):
    stmt = select(Products).options(selectinload(Products.image))
    result = session.execute(stmt)
    products = result.scalars().all()

    if not products:
        return []

    results = []
    for d in products:
        image_data = None
        if d.image:
            image_data = {
                "ID": d.image.product_id,
                "Path_Image": d.image.image_url,
            }

        results.append(
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "price": d.price,
                "quantity": d.quantity,
                "category_id": d.category_id,
                "is_active": d.is_active,
                "created_at": d.created_at,
                "image": image_data,
            }
        )

    return results


@app.get("/products", status_code=SUCCESS)
async def get_products(
    search: str | None = None,
    category_id: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    session: Session = GetDB,
):
    stmt = select(Products)

    if search:
        stmt = stmt.where(
            or_(
                Products.name.ilike(f"%{search}%"),
                Products.description.ilike(f"%{search}%"),
            )
        )

    if category_id:
        stmt = stmt.where(Products.category_id == category_id)

    if min_price is not None:
        stmt = stmt.where(Products.price >= min_price)

    if max_price is not None:
        stmt = stmt.where(Products.price <= max_price)

    result = session.execute(stmt)
    products = result.scalars().all()

    return {"total": len(products), "products": products}


@app.get("/products/{id}", SUCCESS)
async def GetProduct(id: str, session: Session = GetDB):
    if not id:
        raise HTTPException(
            status_code=BAD_REQUEST, detail="Please , check your request data"
        )

    result = session.execute(select(Products).where(Products.id == id))
    get_product = result.scalar_one_or_none()

    if get_product:
        return get_product


@app.post("/products", status_code=CREATED)
async def AddProduct(
    products: ProductsModel,
    session: Session = GetDB,
):
    name = products.name
    description = products.description
    price = products.price
    quantity = products.quantity
    category_id = products.category_id

    if not name or not description or not price or not category_id or not quantity:
        raise HTTPException(
            status_code=BAD_REQUEST, detail="Please check the data request !"
        )

    add_product = Products(
        name=name,
        description=description,
        price=price,
        quantity=quantity,
        category_id=category_id,
    )
    try:
        session.add(add_product)
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=ERROR_SERVER, detail=f"Error : {e}")


@app.post("/products/UploadFile/{id}", status_code=CREATED)
async def UploadFileProduct(
    id: str, session: Session = GetDB, file: UploadFile = File(...)
):
    ext = str(file.filename).rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error image"
        )

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصورة كبير جدًا (الحد 5MB).")

    try:
        img = Image.open(BytesIO(content))
        img = img.convert("RGB") if img.mode in ("RGBA", "p") else img
        img = img.resize((200, 200))
    except:
        raise HTTPException(status_code=400, detail="ملف الصورة تالف أو غير صالح.")

    unique_filename = f"{uuid.uuid4().hex}.jpg"
    file_path = f"{UPLOAD_FOLDER}/{unique_filename}"
    img.save(file_path, format="JPEG", quality=85)

    add_image = ProductImages(product_id=id, image_url=file_path)
    try:
        session.add(add_image)
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=ERROR_SERVER, detail=f"Error : {e}")

    return {
        "message": "File saved",
        "path": file_path,
        "filename": file.filename,
        "content_type": file.content_type,
    }


@app.put("/products/{id}", status_code=SUCCESS)
async def UpdateProduct(id: str, update: UpdateProductsModel, session: Session = GetDB):
    if not id:
        raise HTTPException(
            status_code=BAD_REQUEST, detail="Please , check your request data"
        )

    name = update.name
    description = update.description
    price = update.price
    quantity = update.quantity

    if not name and not description and not price and not quantity:
        raise HTTPException(
            status_code=BAD_REQUEST, detail="Please , check your request data"
        )

    result = session.execute(select(Products).where(Products.id == id))
    update_product = result.scalar_one_or_none()

    if update_product:
        update_product.name = name
        update_product.description = description
        update_product.price = price
        update_product.quantity = quantity

        session.commit()

        return {
            "Message": "Update successfully",
            "ID": id,
        }


@app.delete("/products/{id}", status_code=DELETED)
async def DeleteProduct(id: str, session: Session = GetDB):
    if not id:
        raise HTTPException(
            status_code=BAD_REQUEST, detail="Please , check your request data"
        )

    result = session.execute(select(Products).where(Products.id == id))
    delete_product = result.scalar_one_or_none()
    if delete_product:
        session.delete(delete_product)
        session.commit()

        return {"Message": "Deleted successfully", "ID": id}


@app.get("/categories", status_code=SUCCESS)
async def GetAllCategories(session: Session = GetDB):
    result = session.execute(select(Categories))
    GetAllCategories = result.scalars().all()

    return GetAllCategories


@app.post("/categories", status_code=CREATED)
async def AddCategories(categories: CategoriesModel, session: Session = GetDB):
    name = categories.name
    description = categories.description

    if not name or not description:
        raise HTTPException(
            status_code=BAD_REQUEST, detail="Please check the data request !"
        )

    add_categories = Categories(name=name, description=description)

    try:
        session.add(add_categories)
        session.commit()

        return {"Message": "Added categories successfully", "Name Categories": name}
    except Exception as e:
        raise HTTPException(status_code=ERROR_SERVER, detail=f"Error : {e}")
