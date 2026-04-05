from pydantic import BaseModel
from typing import List, Optional

# MENU schema:
class ProductOptionCreate(BaseModel):
    group_name: str           # e.g., "Milk"
    value: str          # e.g., "Oat"
    extra_price: int    # e.g., 50


class ProductCreate(BaseModel):
    name: str
    category: str
    price: int
    options: List[ProductOptionCreate] = []


class OrderOptionCreate(BaseModel):
    # The ID of the option the user clicked in the dropdown
    product_option_id: int

class OrderItemCreate(BaseModel):
    # The ID of the coffee/drink
    product_id: int
    # The list of option IDs chosen for this specific drink
    options: List[OrderOptionCreate] = []

class OrderCreate(BaseModel):
    location: str
    items: List[OrderItemCreate]