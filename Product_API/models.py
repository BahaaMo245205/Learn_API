
from pydantic import BaseModel, Field


class CategoriesModel(BaseModel):
    name: str
    description: str


class ProductsModel(BaseModel):
    name: str = Field(..., min_length=2)
    description: str
    price: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    category_id: str


class UpdateProductsModel(BaseModel):
    name: str = Field(..., min_length=2)
    description: str
    price: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


