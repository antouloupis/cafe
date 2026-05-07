from fastapi import APIRouter, Depends, Form, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, SQLModel, col, delete
from database import get_session
from models import Category, Product, ProductOption, AdminUser, Order, OrderItem, OrderItemOption
from utils import hash_password, templates
from typing import List
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from sqlalchemy.orm import selectinload
from constants import CAFE_STATE

# We don't use a strict prefix here because /login and /logout sit at the root level,
# but we will manually prefix the inventory routes with /admin/
router = APIRouter(tags=["Admin"])

class PasswordChangeSchema(SQLModel):
    new_password: str


# --- TOGGLE CAFE OPEN ---
@router.post("/admin/toggle-cafe")
def toggle_cafe(request: Request):
    # Toggle the boolean inside the shared dictionary
    CAFE_STATE["is_open"] = not CAFE_STATE["is_open"]
    
    status_text = "ΑΝΟΙΧΤΟ" if CAFE_STATE["is_open"] else "ΚΛΕΙΣΤΟ"
    dot_color = "bg-green-500" if CAFE_STATE["is_open"] else "bg-red-500"
    
    # Return the HTML for your HTMX swap
    return HTMLResponse(content=f'''
        <div class="h-3 w-3 rounded-full {dot_color}"></div>
        <span class="text-xs font-black uppercase text-white">{status_text}</span>
    ''')

# --- AUTH & DASHBOARD ---

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_session)):
    session_cookie = request.cookies.get("kylikeio_session")
    if not session_cookie:
        return templates.TemplateResponse(request=request, name="login.html")
    products = db.exec(select(Product)).all()
    categories = db.exec(select(Category)).all()
    return templates.TemplateResponse(
        request=request,
        name="product_admin.html",
        context={ "products": products, "categories": categories, "CAFE_STATUS": CAFE_STATE["is_open"]})

@router.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_session)):
    admin = db.exec(select(AdminUser).where(AdminUser.username == username)).first()
    if not admin or admin.hashed_password != hash_password(password):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Λάθος στοιχεία σύνδεσης"})
        
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
    # 1. Change to default=None so FastAPI doesn't block the request
    name: str | None = Form(default=None),
    category_id: int | None = Form(default=None),
    price: float | None = Form(default=None),
    
    opt_group: list[str] = Form(default=[]),
    opt_val: list[str] = Form(default=[]),
    opt_price: list[float] = Form(default=[]),
    db: Session = Depends(get_session)
):
    check_admin(request)

    missing = []
    if not name:
        missing.append("Όνομα")
    if category_id is None:
        missing.append("Κατηγορία")
    if price is None:
        missing.append("Τιμή")

    # --- THE HTMX RETARGET FIX ---
    if missing:
        msg = f"Λείπουν τα εξής πεδία: {', '.join(missing)}"
            
        # Create a nice red error box
        error_html = f"""
        <div class="p-3 bg-red-100 border border-red-400 text-red-700 font-bold rounded shadow-sm">
        ⚠️ Προσοχή: {msg}
        </div>
        """
            
        return HTMLResponse(
            content=error_html, 
            headers={
                "HX-Retarget": "#form-errors", # Send the error to the new div
                "HX-Reswap": "innerHTML"       # Put it inside the div
            }
        )

    # 4. If everything is good, continue creating the product as normal
    product = Product(name=name, category_id=category_id, price=price)
    db.add(product)
    db.flush() 

    for g, v, p in zip(opt_group, opt_val, opt_price):
        new_option = ProductOption(
            product_id=product.id,
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
    session_cookie = request.cookies.get("kylikeio_session")
    if not session_cookie:
        return templates.TemplateResponse(request=request, name="login.html")
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

    now = datetime.now(timezone.utc)

    orders_data = []

    for order in orders:
        # 2. Extract the creation time
        order_time = order.created_at
        
        # 3. Safely re-attach the UTC timezone if the database stripped it
        if order_time.tzinfo is None:
            order_time = order_time.replace(tzinfo=timezone.utc)

        # 4. Calculate the delta (this results in a timedelta object)
        time_delta = now - order_time
        
        # 5. Convert the delta to total minutes
        minutes_passed = int(time_delta.total_seconds() / 60)
        
        # 6. Format it for the barista
        if minutes_passed < 1:
            time_str = "Τώρα"
        elif minutes_passed < 60:
            time_str = f"{minutes_passed}λ"
        else:
            hours = int(minutes_passed / 60)
            time_str = f"{hours}ω"

        # 7. Append to a dictionary to avoid Pydantic Model errors
        orders_data.append({
            "order": order,
            "minutes_passed": minutes_passed,
            "time_str": time_str
        })
    context = {
        "request": request,
        "orders_data": orders_data,
        "current_status": status,
        "CAFE_STATUS": CAFE_STATE["is_open"],
        "title": "Παραγγελίες",

    }
    headers = {}
    is_htmx = request.headers.get("HX-Request")
    
    if is_htmx and status in ["pending", "all"] and orders:
        newest_order = orders[0]
        
        # 2. Make it timezone aware for comparison
        dt_aware = newest_order.created_at
        if dt_aware.tzinfo is None:
            dt_aware = dt_aware.replace(tzinfo=timezone.utc)
        
        # 3. Calculate age in seconds
        order_age_seconds = (now - dt_aware).total_seconds()
        
        # 4. Trigger only if it's a "New Arrival" 
        if 0 <= order_age_seconds <= 12:
            headers["HX-Trigger"] = "newOrder"
    
    # If it's an HTMX poll/request, only return the table rows
    if is_htmx:
        return templates.TemplateResponse(
            name="partials/admin_orders_list.html", 
            context=context,
            headers=headers,
            request=request
        )

    # Full page load
    return templates.TemplateResponse(
        name="orders_dashboard.html", 
        context=context,
        request=request
    )

@router.post("/admin/order/{order_id}/change_status")
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


    return HTMLResponse(
            content="""
            <div class="text-gray-400 text-center my-auto">Επέλεξε παραγγελία για να δείς λεπτομέρειες</div>
            """,
            headers={"HX-Trigger": "orderChanged"}
        )

@router.get("/admin/order/{order_id}/details")
async def get_order_details(request: Request,order_id: int, db: Session = Depends(get_session)):
    # 1. Fetch Order + Items + Options in one query
    statement = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.options))
    )
    order_obj = db.exec(statement).first()

    if not order_obj:
        return HTMLResponse("Order not found", status_code=404)

    # 2. Group options by category (group_name)
    display_items = []
    for item in order_obj.items:
        grouped = defaultdict(list)
        for opt in item.options:
            grouped[opt.group_name].append(opt.value)
        
        display_items.append({
            "name": item.name,
            "quantity": item.quantity,
            "grouped_options": dict(grouped)
        })

    # 3. Return only the relevant data
    return templates.TemplateResponse(
        name="partials/admin_selected_order.html",  # Explicitly name the template
        request=request,
        context={ 
            "selected_order": order_obj, 
            "display_items": display_items
        }
    )


def get_weekly_stats(db: Session):
    query = select(Order).where(Order.status == "completed")
    completed_orders = db.exec(query).all()

    total_revenue = 0.0
    product_breakdown = {}
    location_breakdown = {} 

    for order in completed_orders:
        total_revenue += order.total
        
        loc = order.location
        if loc not in location_breakdown:
            location_breakdown[loc] = {"orders": 0, "revenue": 0.0}
        
        location_breakdown[loc]["orders"] += 1
        location_breakdown[loc]["revenue"] += order.total

        for item in order.items:
            name = item.name
            if name not in product_breakdown:
                product_breakdown[name] = {"quantity": 0, "revenue": 0.0}
            
            product_breakdown[name]["quantity"] += item.quantity
            product_breakdown[name]["revenue"] += item.total

    sorted_products = sorted(
        product_breakdown.items(), 
        key=lambda x: x[1]["revenue"], 
        reverse=True
    )

    # 4. Grab BOTH the name and the stats using a dictionary
    top_by_amount = {"name": "Καμία", "orders": 0}
    top_by_income = {"name": "Καμία", "revenue": 0.0}
    
    if location_breakdown:
        # max() returns a tuple like ('Υπασπιστήριο', {'orders': 15, 'revenue': 45.5})
        amt_winner = max(location_breakdown.items(), key=lambda x: x[1]["orders"])
        top_by_amount = {"name": amt_winner[0], "orders": amt_winner[1]["orders"]}

        inc_winner = max(location_breakdown.items(), key=lambda x: x[1]["revenue"])
        top_by_income = {"name": inc_winner[0], "revenue": round(inc_winner[1]["revenue"], 2)}

    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": len(completed_orders),
        "products": sorted_products,
        "top_amount": top_by_amount,
        "top_income": top_by_income
    }

@router.get("/admin/statistics")
def admin_statistics(request: Request, db: Session = Depends(get_session)):
    
    # Get the stats dictionary
    stats = get_weekly_stats(db)

    # THE FIX: Explicitly name the arguments!
    return templates.TemplateResponse(
        request=request,
        name="admin_stats.html", 
        context={
            "request": request, 
            "stats": stats,
            "CAFE_STATUS": CAFE_STATE["is_open"],
            "title": "Στατιστικά εβδομάδας",

        }
    )
