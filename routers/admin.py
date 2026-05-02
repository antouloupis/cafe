from fastapi import APIRouter, Depends, Form, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, SQLModel, col
from database import get_session
from models import Category, Product, ProductOption, AdminUser, Order, OrderItem, OrderItemOption
from utils import hash_password, templates
from typing import List

# We don't use a strict prefix here because /login and /logout sit at the root level,
# but we will manually prefix the inventory routes with /admin/
router = APIRouter(tags=["Admin"])

class PasswordChangeSchema(SQLModel):
    new_password: str

CAFE_OPEN_STATUS = False

# --- TOGGLE CAFE OPEN ---
@router.post("/admin/toggle-cafe")
def toggle_cafe(request : Request):
    check_admin(request)
    global CAFE_OPEN_STATUS
    CAFE_OPEN_STATUS = not CAFE_OPEN_STATUS
    return HTMLResponse("Open" if CAFE_OPEN_STATUS else "Closed")

# --- AUTH & DASHBOARD ---

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_session)):
    session_cookie = request.cookies.get("kylikeio_session")
    if not session_cookie:
        return templates.TemplateResponse(request=request, name="login.html")
    products = db.exec(select(Product)).all()
    categories = db.exec(select(Category)).all()
    return templates.TemplateResponse(request=request, name="product_admin.html", context={"title": "Admin Dashboard", "products": products, "categories": categories})

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

@router.post("/admin/product/create")
def create_product(
    request: Request, 
    name: str = Form(...),
    category_id: int = Form(...),
    price: float = Form(...),
    # Add these to catch the "Drafted" options from JS
    opt_group: list[str] = Form(default=[]),
    opt_val: list[str] = Form(default=[]),
    opt_price: list[float] = Form(default=[]),
    db: Session = Depends(get_session)
):
    check_admin(request)

    # 1. Create the Product
    product = Product(name=name, category_id=category_id, price=price)
    db.add(product)
    
    # 2. Flush to get the ID without committing yet
    db.flush() 

    # 3. Create the options and link them to the new ID
    for g, v, p in zip(opt_group, opt_val, opt_price):
        new_option = ProductOption(
            product_id=product.id, # Now we have an ID!
            group_name=g,
            value=v,
            extra_price=p
        )
        db.add(new_option)

    db.commit()
    db.refresh(product)

    return HTMLResponse("<script>document.getElementById('edit-modal').remove();</script>", headers={"HX-Trigger": "productUpdated"})

@router.get("/admin/product/create")
def get_create_form(request: Request, db: Session = Depends(get_session)):
    check_admin(request)
    mTitle = f"Δημιουργία νέου προϊόντος"
    submitUrl = "/admin/product/create"
    categories = db.exec(select(Category)).all()

    return templates.TemplateResponse(
        request=request, 
        name="partials/product_modal.html", # A new file containing just the expanded HTML
        context={"product":{},"categories": categories, "modal": {"title": mTitle, "btn": "Δημιουργία Προϊόντος", "submitUrl": submitUrl}}
    )


@router.delete("/admin/product/{product_id}/delete")
def delete_product(request: Request, product_id: int, db: Session = Depends(get_session)):
    check_admin(request)
    product = db.get(Product, product_id)
    if not product:
        return {"error": "Not found"}
    db.delete(product)
    db.commit()
    return HTMLResponse(f'<p class="z-10 bg-green-500 text-white p-4 rounded-md shadow-md text-center">Product deleted successfully.</p>', headers={"HX-Trigger": "productUpdated"})


@router.post("/admin/product/{product_id}/add_option")
def add_option(
    request: Request,
    product_id: int,
    group_name: str = Form(...),
    value: str = Form(...),
    extra_price: float = Form(...),
    db: Session = Depends(get_session)):
    
    check_admin(request)
    option = ProductOption(product_id=product_id, group_name=group_name, value=value, extra_price=extra_price)
    db.add(option)
    db.commit()
    html_row = f"""
            <div class="option-row" style="display: flex; gap: 10px; margin-bottom: 10px;">
                <input type="hidden" name="opt_id" value="{option.id}">
                <input type="text" name="opt_group" value="{option.group_name}">
                <input type="text" name="opt_val" value="{option.value}">
                <input type="number" name="opt_price" value="{option.extra_price}">
                <button type="button" style="color: red;" onclick="this.closest('.option-row').remove()">🗑️</button>
            </div>
        """
    return HTMLResponse(html_row)

@router.post("/admin/product/{product_id}/full-update")
def update_product_full(
    request: Request,
    product_id: int,
    name: str = Form(...),
    category_id: int = Form(...),
    price: float = Form(...),
    opt_id: List[int] = Form(default=[]),
    opt_group: List[str] = Form(default=[]),
    opt_val: List[str] = Form(default=[]),
    opt_price: List[float] = Form(default=[]),
    db: Session = Depends(get_session)
):
    check_admin(request)
    
    # 1. Update main product
    product = db.get(Product, product_id)
    product.name = name
    product.category_id = category_id
    product.price = price
    db.add(product)
    
    # 2. Update existing options
    existing_options = db.exec(select(ProductOption).where(ProductOption.product_id == product_id)).all()
    submitted_ids = [oid for oid in opt_id if oid > 0] # Filter out the 0s/new ones

    # Delete: If it's in the DB but NOT in the submitted list, kill it
    for opt in existing_options:
        if opt.id not in submitted_ids:
            db.delete(opt)

    # Update or Create: Loop through the submitted lists
    for oid, ogroup, oval, oprice in zip(opt_id, opt_group, opt_val, opt_price):
        if oid > 0:
            # UPDATE existing
            existing = db.get(ProductOption,oid)
            if existing:
                existing.group_name = ogroup
                existing.value = oval
                existing.extra_price = oprice
                db.add(existing)
        else:
            # CREATE new
            new_opt = ProductOption(
                product_id=product_id,
                group_name=ogroup,
                value=oval,
                extra_price=oprice
            )
            db.add(new_opt)

    db.commit()
    return HTMLResponse("<script>document.getElementById('edit-modal').remove();</script>", headers={"HX-Trigger": "productUpdated"})


@router.get("/admin/product/{product_id}/edit", response_class=HTMLResponse)
def get_edit_form(request: Request, product_id: int, db: Session = Depends(get_session)):
    check_admin(request)
    product = db.get(Product, product_id)
    mTitle = f"Επεξεργασία: {product.name}"
    submitUrl = f"/admin/product/{product_id}/full-update"
    categories = db.exec(select(Category)).all()
    return templates.TemplateResponse(
        request=request, 
        name="partials/product_modal.html", # A new file containing just the expanded HTML
        context={"categories": categories, "product": product, "modal": {"title": mTitle, "btn": "Αποθήκευση", "submitUrl": submitUrl}}
    )


@router.get("/admin/product-list", response_class=HTMLResponse)
def get_product_list(request: Request, db: Session = Depends(get_session)):
    check_admin(request) # Security check!
    
    # Fetch all the fresh data
    products = db.exec(select(Product)).all()
    categories = db.exec(select(Category)).all()
    # Return ONLY the partial template, not the whole admin dashboard
    return templates.TemplateResponse(
        request=request, 
        name="partials/product_list.html", 
        context={"request": request, "products": products, "categories": categories}
    )

@router.post("/admin/product/{product_id}/toggle")
def toggle_available(request: Request, product_id: int, db: Session = Depends(get_session)):
    product = db.get(Product, product_id)
    product.available = not product.available
    db.add(product)
    db.commit()
    return Response(status_code=200)

@router.post("/admin/category/create")
def createCategory(request: Request, db: Session= Depends(get_session), catName: str = Form()):
    check_admin(request) # Security check!

    statement = select(Category).where(Category.name == catName)
    existing_category = db.exec(statement).first()

    if existing_category:
        return HTMLResponse("Category already exists!", status_code=400)

    new_category = Category(name=catName)
    db.add(new_category)
    db.commit()
    
    # Refresh the category list in the UI via HTMX
    return Response(
            status_code=204, 
            headers={"HX-Trigger": "productUpdated"}
        )

@router.delete("/admin/category/{category_id}/delete")
def delete_category(request: Request, category_id: int, db: Session = Depends(get_session)):
    check_admin(request)
    cat = db.get(Category, category_id)
    if not cat:
        return HTMLResponse("Category not found", status_code=404)
    
    else:
        db.delete(cat)
        db.commit()
    return Response(
            status_code=204, 
            headers={"HX-Trigger": "productUpdated"}
        )

@router.post("/admin/category/{category_id}/update")
def update_category(category_id: int, catName: str = Form(...), db: Session = Depends(get_session)):
    cat = db.get(Category, category_id)
    if cat:
        cat.name = catName
        db.commit()
    return Response(
            status_code=204, 
            headers={"HX-Trigger": "productUpdated"}
        )


@router.get("/admin/orders")
async def admin_orders(
    request: Request, 
    status: str = "pending", 
    db: Session = Depends(get_session)
):
    check_admin(request)
    # Base Query with Descending Order
    query = select(Order).order_by(col(Order.created_at).desc())
    
    # Filter Logic
    if status == "pending":
        query = query.where(Order.status == "pending")
    elif status == "completed":
        query = query.where(Order.status == "completed")
    elif status == "canceled":
        query = query.where(Order.status == "canceled")

    orders = db.exec(query).all()

    context = {
        "request": request,
        "orders": orders,
        "current_status": status
    }

    # If it's an HTMX poll/request, only return the table rows
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            name="partials/admin_orders_list.html", 
            context=context,
            request=request
            
        )

    # Full page load
    return templates.TemplateResponse(
        name="orders_dashboard.html", 
        context=context,
        request=request
    )

@router.post("/admin/order/{order_id}/status")
async def change_order_status(
    request: Request,
    order_id:int,
    new_status:str,
    current_filter:str = "pending",
    db: Session = Depends(get_session)
):
    check_admin(request)
    order = db.get(Order, order_id)
    if not order:
        return HTMLResponse("Order not found",status_code=404)
    
    order.status = new_status
    db.add(order)
    db.commit()

    query = select(Order).order_by(col(Order.created_at).desc())

    if current_filter == "pending":
        query = query.where(Order.status == "pending")
    elif current_filter == "completed":
        query = query.where(Order.status == "completed")
    elif current_filter == "canceled":
        query = query.where(Order.status == "canceled")

    orders = db.exec(query).all()


    return templates.TemplateResponse(
        name="partials/admin_orders_list.html",
        context={
            "orders": orders,
            "current_status": current_filter
        },
        request=request
    )

