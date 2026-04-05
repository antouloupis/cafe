from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime, timezone


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str
    price: int
    options: List["ProductOption"] = Relationship(back_populates="product")
    

class ProductOption(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    group_name: str
    value: str
    extra_price: int
    product: Product = Relationship(back_populates="options")

#ORDER TABLES

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # customer_name: str
    location: str
    status: str = "pending"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    items: List["OrderItem"] = Relationship(back_populates="order")

class OrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: int
    order_id: int = Field(foreign_key="order.id")
    order: "Order" = Relationship(back_populates="items")
    options: List["OrderItemOption"] = Relationship(back_populates="order_item")

class OrderItemOption(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_item_id: int = Field(foreign_key="orderitem.id")
    group_name: str
    value: str
    extra_cost: int
    order_item: OrderItem = Relationship(back_populates="options")

    #admin
class AdminUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, default="admin")
    hashed_password: str