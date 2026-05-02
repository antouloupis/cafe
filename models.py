from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime, timezone


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    price: float = Field(ge=0)
    available: bool = Field(default=True)
    options: List["ProductOption"] = Relationship(
        back_populates="product",
        cascade_delete=True)
    category: Optional["Category"] = Relationship(back_populates="products")

class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True) # "unique" prevents the duplicate names!
    products: List["Product"] = Relationship(back_populates="category")
    

class ProductOption(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(
        foreign_key="product.id",
        ondelete="CASCADE")
    group_name: str
    value: str
    extra_price: float = Field(ge=0)
    product: Product = Relationship(back_populates="options")

#ORDER TABLES

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    location: str
    status: str = "pending"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    items: List["OrderItem"] = Relationship(back_populates="order")

class OrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float
    quantity: int = Field(default=1,ge=1)
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