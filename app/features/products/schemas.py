from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ProductC(BaseModel):
    manufacturer: str
    name: str
    dimensions: Optional[str] = None
    unit: str
    price: Decimal
    quantity_available: int = 0
    image_path: Optional[str] = None

class PrCreate(ProductC):
    pass

class PrUpdate(BaseModel):
    manufacturer: Optional[str] = None
    name: Optional[str] = None
    dimensions: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[Decimal] = None
    quantity_available: Optional[int] = None
    image_path: Optional[str] = None

class PrRead(ProductC):
    product_id: int
    model_config = ConfigDict(from_attributes=True)
