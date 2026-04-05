from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, SQLModel
from database import get_session
from models import Product, ProductOption, AdminUser
from schemas import ProductCreate, ProductOptionCreate # Assuming these are in schemas.py
from utils import hash_password, templates

# We don't use a strict prefix here because /login and /logout sit at the root level,
# but we will manually prefix the inventory routes with /admin/
router = APIRouter(tags=["Admin"])

class PasswordChangeSchema(SQLModel):
    new_password: str

# --- AUTH & DASHBOARD ---

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    session_cookie = request.cookies.get("kylikeio_session")
    if not session_cookie:
        return templates.TemplateResponse(request=request, name="login.html")
    return templates.TemplateResponse(request=request, name="admin.html", context={"title": "Admin Dashboard"})

@router.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_session)):
    admin = db.exec(select(AdminUser).where(AdminUser.username == username)).first()
    if not admin or admin.hashed_password != hash_password(password):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Invalid credentials"})
        
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(key="kylikeio_session", value="authenticated_admin_token", httponly=True)
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/admin", status_code=303)
    response.delete_cookie("kylikeio_session")
    return response

@router.post("/admin/change-password")
def change_password(data: PasswordChangeSchema, db: Session = Depends(get_session)):
    admin = db.exec(select(AdminUser).where(AdminUser.username == "admin")).first()
    admin.hashed_password = hash_password(data.new_password)
    db.add(admin)
    db.commit()
    return {"status": "Password updated in database"}

# --- INVENTORY MANAGEMENT (Protected) ---

# Helper function to check auth on API routes
def check_admin(request: Request):
    if not request.cookies.get("kylikeio_session"):
        raise HTTPException(status_code=403, detail="Unauthorized")

@router.post("/admin/product")
def create_product(request: Request, product_data: ProductCreate, db: Session = Depends(get_session)):
    check_admin(request) # Security gate
    
    product = Product(name=product_data.name, category=product_data.category, price=product_data.price)
    db.add(product)
    db.commit()
    db.refresh(product)

    for opt in product_data.options:
        option = ProductOption(product_id=product.id, group_name=opt.group_name, value=opt.value, extra_price=opt.extra_price)
        db.add(option)
    db.commit()
    return product

@router.delete("/admin/product/{product_id}")
def delete_product(request: Request, product_id: int, db: Session = Depends(get_session)):
    check_admin(request)
    product = db.get(Product, product_id)
    if not product:
        return {"error": "Not found"}
    db.delete(product)
    db.commit()
    return {"status": "deleted"}

@router.put("/admin/product/{product_id}")
def update_product(request: Request, product_id: int, data: dict, db: Session = Depends(get_session)):
    check_admin(request)
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

@router.post("/admin/product/{product_id}/options")
def add_option(request: Request, product_id: int, data: ProductOptionCreate, db: Session = Depends(get_session)):
    check_admin(request)
    option = ProductOption(product_id=product_id, group_name=data.group_name, value=data.value, extra_price=data.extra_price)
    db.add(option)
    db.commit()
    return {"status": "option added"}