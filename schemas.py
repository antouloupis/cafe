from pydantic import BaseModel
from typing import List, Optional

# MENU schema:
class ProductOption(BaseModel):
    name: str           # e.g., "Milk"
    value: str          # e.g., "Oat"
    extra_price: int    # e.g., 50

class Product(BaseModel):
    product_name: str   # e.g., "Latte"
    base_price: int     # e.g., 350
    chosen_options: List[MenuItemOption] = []

# ORDER schema:
class Order(BaseModel):
    customer_name: str
    location: str
    items: List[MenuItem]

class OrderItemOption(BaseModel):
    name: str            # e.g., "Milk Type"
    value: str           # e.g., "Oat"
    extra_cost: int      # <--- Copied from MenuOption.price_modifier


class OrderItem(BaseModel):
    product_name: str    # <--- Copied from Product.name
    unit_price: int      # <--- Copied from Product.base_price at time of order
    options: List[OrderItemOption] = []