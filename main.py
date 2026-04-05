from fastapi import FastAPI, Depends, Form, Request
from database import init_db,engine
from models import Product, ProductOption, Order, OrderItem, OrderItemOption,AdminUser
import os
import hashlib
from sqlmodel import Session, select, SQLModel
from database import get_session
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
# -------------------
from schemas import ProductCreate


app = FastAPI()
templates = Jinja2Templates(directory="templates")

class PasswordChangeSchema(SQLModel):
    new_password: str

def hash_password(password: str):
    # Standard SHA-256 for air-gapped environments
    return hashlib.sha256(password.encode()).hexdigest()


@app.on_event("startup")
def on_startup():
    # This ensures the .db file and tables are created inside the Docker volume
    init_db()


    with Session(engine) as session:
            # Check if the admin already exists in the DB
            existing_admin = session.exec(select(AdminUser).where(AdminUser.username == "admin")).first()
            
            if not existing_admin:
                # First run! Grab from .env
                env_pass = os.getenv("ADMIN_PASSWORD")
                if env_pass:
                    print("--- FIRST RUN: Creating Admin from .env ---")
                    new_admin = AdminUser(hashed_password=hash_password(env_pass))
                    session.add(new_admin)
                    session.commit()
                else:
                    print("--- WARNING: No Admin and no .env password found! ---")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_session)):
    products = db.exec(select(Product)).all()

    return templates.TemplateResponse(
        request=request,
        name="menu.html",
        context={"products": products} 
    )


@app.post("/admin/change-password")
def change_password(data: PasswordChangeSchema, db: Session = Depends(get_session)):
    # 1. Fetch the admin
    admin = db.exec(select(AdminUser).where(AdminUser.username == "admin")).first()
    
    # 2. Update with the new hash
    admin.hashed_password = hash_password(data.new_password)
    db.add(admin)
    db.commit()
    
    return {"status": "Password updated in database"}


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # Check if the browser sent the secret cookie
    session_cookie = request.cookies.get("kylikeio_session")
    
    if not session_cookie:
        # No cookie? Show them the login page instead.
        return templates.TemplateResponse(
            request=request, 
            name="login.html"
        )
        
    # Valid cookie? Welcome to the VIP area.
    return templates.TemplateResponse(
        request=request, 
        name="admin.html", 
        context={"title": "Admin Dashboard"}
    )


@app.post("/login")
async def login_post(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_session)
):
    # Fetch admin from DB
    admin = db.exec(select(AdminUser).where(AdminUser.username == username)).first()
    
    # Check if admin exists AND password matches your hash function
    if not admin or admin.hashed_password != hash_password(password):
        # Fail: Send them back to login with an error
        return templates.TemplateResponse(
            request=request, 
            name="login.html", 
            context={"error": "Invalid username or password"}
        )
        
    # Success! Create a redirect response to send them to the dashboard
    response = RedirectResponse(url="/admin", status_code=303)
    
    # Set the secure cookie. 
    # (In a real production environment, you'd use a unique session token here)
    response.set_cookie(
        key="kylikeio_session", 
        value="authenticated_admin_token", 
        httponly=True # This stops hackers from reading the cookie with JavaScript
    )
    
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/admin", status_code=303)
    # Destroy the cookie
    response.delete_cookie("kylikeio_session")
    return response

# -------------------prosthetw--------------------------------------

@app.get("/menu")
def get_menu(db: Session = Depends(get_session)):
    products = db.exec(select(Product)).all()
    return products



#ADD MENU ITEM
@app.post("/menu")
def create_product(product_data: ProductCreate, db: Session = Depends(get_session)):
    product = Product(
        name=product_data.name,
        category=product_data.category,
        price=product_data.price
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    # Add options (extras)
    for opt in product_data.options:
        option = ProductOption(
            product_id=product.id,
            group_name=opt.group_name,
            value=opt.value,
            extra_price=opt.extra_price
        )
        db.add(option)

    db.commit()

    return product

# DELETE MENU ITEM
@app.delete("/menu/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_session)):
    product = db.get(Product, product_id)

    if not product:
        return {"error": "Not found"}

    db.delete(product)
    db.commit()

    return {"status": "deleted"}

# UPDATE MENU ITEM
@app.put("/menu/{product_id}")
def update_product(product_id: int, data: dict, db: Session = Depends(get_session)):
    product = db.get(Product, product_id)

    if not product:
        return {"error": "Not found"}

    if "price" in data:
        product.price = data["price"]

    if "category" in data:
        product.category = data["category"]

    db.add(product)
    db.commit()

    return {"status": "updated"}

#GET OPTIONS
@app.get("/menu/{product_id}/options")
def get_options(product_id: int, db: Session = Depends(get_session)):
    options = db.exec(
        select(ProductOption).where(ProductOption.product_id == product_id)
    ).all()

    return options


#ADD OPTION
@app.post("/menu/{product_id}/options")
def add_option(product_id: int, data: ProductOptionCreate, db: Session = Depends(get_session)):
    option = ProductOption(
        product_id=product_id,
        group_name=data.group_name,
        value=data.value,
        extra_price=data.extra_price
    )

    db.add(option)
    db.commit()

    return {"status": "option added"}