from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from sqlmodel import Session, select
from database import get_session
from models import Product, Category, Order, OrderItem, OrderItemOption
from utils import templates
from constants import CAFE_STATE

router = APIRouter(tags=["Menu"])

cart = []

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_session)):
    categories = db.exec(select(Category)).all()
    # Group products by category

    if not CAFE_STATE["is_open"]:
            return templates.TemplateResponse(
            name="closed.html",
            request= request, 
            status_code=503
        )

    # open case
    return templates.TemplateResponse(
        name="menu.html",
        request= request,
        context={
            
            "categories": categories,
            "title": "Coffee Menu",
            "cart": cart
        }
    )

@router.get("/product-options/{product_id}")
async def product_options(request: Request, product_id: int, db: Session = Depends(get_session)):
    product = db.get(Product, product_id)
    if not product:
        return Response("Product not found", status_code=404)

    return templates.TemplateResponse(
        request=request,
        name="partials/menu_product.html",
        context={"product": product} # You don't even need "request" in the dict anymore if you pass it as a kwarg!
    )



@router.post("/add-to-cart/{product_id}")
async def add_to_cart(
    product_id: int,
    extras: list[int] = Form(default=[])
):
    # Sort extras for comparison
    extras_sorted = sorted(extras)

    # Check if same product + same extras already exists
    for item in cart:
        if item["id"] == product_id and sorted(item.get("extras", [])) == extras_sorted:
            item["qty"] += 1
            break
    else:
        cart.append({
            "id": product_id,
            "qty": 1,
            "extras": extras_sorted
        })


    return Response(
    """
    <div class="text-center py-6 space-y-4">
        <div class="text-4xl">✅</div>
        <p class="text-xl font-bold text-[#2f3517] uppercase">Προστέθηκε στο καλάθι</p>
        <button
            type="button"
            onclick="document.getElementById('modal').style.display='none'"
            class="bg-[#556b2f] text-white text-2xl px-5 py-3 font-bold uppercase tracking-wider cursor-pointer">
            Κλείσιμο
        </button>
    </div>
    """,
    media_type="text/html"
    )


@router.get("/cart")
async def show_cart(request: Request, db: Session = Depends(get_session)):
    cart_items = []
    grand_total = 0.0

    # 1. Prepare data
    for item in cart:
        product = db.get(Product, item["id"])
        if not product: continue
        
        item_extras = []
        unit_price = float(product.price)
        
        for e_id in item.get("extras", []):
            extra = next((o for o in product.options if o.id == e_id), None)
            if extra:
                item_extras.append(extra)
                unit_price += float(extra.extra_price)
        
        total = unit_price * item["qty"]
        grand_total += total
        cart_items.append({
            "product": product,
            "qty": item["qty"],
            "extras": item_extras,
            "total": total
        })

    context = {
        "request": request,
        "cart_items": cart_items,
        "grand_total": grand_total,
        "cart": cart
    }

    return templates.TemplateResponse(
      request=request,
      name="partials/cart_page.html",
      context=context
    )

@router.post("/place-order")
async def place_order(
    request: Request,
    location: str = Form(...),
    comment: str = Form(None),  # Add this to catch the textarea input
    db: Session = Depends(get_session)
):
    if not cart:
        return HTMLResponse("<p class='text-center py-10'>Το καλάθι είναι άδειο 🥲</p>")

    try:
        location_map = {
            "1": "1ο Γραφείο", "2": "2ο Γραφείο", "3": "3ο Γραφείο",
            "4": "4ο Γραφείο", "5": "Γραφείο Έρευνας Πληροφορικής",
            "6": "Υπασπιστήριο", "7": "Επιτελάρχης", "8": "Συντονιστής",
            "9": "Υποδιοικητής",
        }
        location_label = location_map.get(location, location)

        # 1. Include the comments here during initialization
        new_order = Order(
            location=location_label, 
            status="pending", 
            comment=comment, # Save the textarea content
            total=0.0          # Placeholder
        )
        db.add(new_order)
        db.flush() 

        grand_total = 0.0

        for item in cart:
            product = db.get(Product, item["id"])
            if not product: continue

            base_price = float(product.price)
            item_unit_price = base_price

            order_item = OrderItem(
                name=product.name,
                price=base_price,
                quantity=item["qty"],
                order_id=new_order.id,
                total=base_price
            )
            db.add(order_item)
            db.flush()

            if "extras" in item and item["extras"]:
                for extra_id in item["extras"]:
                    extra = next((opt for opt in product.options if opt.id == extra_id), None)
                    if extra:
                        item_unit_price += float(extra.extra_price)
                        db.add(OrderItemOption(
                            order_item_id=order_item.id,
                            group_name=extra.group_name,
                            value=extra.value,
                            extra_cost=extra.extra_price
                        ))

            order_item.total = item_unit_price
            item_total = item_unit_price * item["qty"]
            grand_total += item_total

        # 2. Update the parent order with the final calculated total
        new_order.total = grand_total
        
        # 3. Finalize Transaction
        db.commit()
        
        cart.clear()

        response = Response(status_code=204)
        response.set_cookie(key="last_order_id", value=str(new_order.id), max_age=3600)
        response.headers["HX-Redirect"] = "/order-complete"
        return response

    except Exception as e:
        db.rollback()
        print(f"DATABASE ERROR: {e}")
        return HTMLResponse(
            "<div class='bg-red-100 p-4 text-red-700'>Σφάλμα κατά την καταχώρηση.</div>", 
            status_code=500
        )
    

@router.get("/order-complete")
async def show_order_complete(request: Request, db: Session = Depends(get_session)):
    # 1. Check the cookie
    order_id = request.cookies.get("last_order_id")
    if not order_id:
        return RedirectResponse(url="/")

    # 2. Fetch the order from the database
    order = db.get(Order, int(order_id))
    if not order:
        return RedirectResponse(url="/")

    # 3. Prepare the data exactly like your old success return did
    template_items = []
    grand_total = 0.0

    for item in order.items:
        # Calculate options total
        options_cost = sum(opt.extra_cost for opt in item.options)
        item_total = (item.price + options_cost) * item.quantity
        grand_total += item_total
        
        template_items.append({
            "name": item.name,
            "qty": item.quantity,
            "total": item_total,
            "extras": [{"group": o.group_name, "val": o.value, "price": o.extra_cost} for o in item.options]
        })

    # 4. Return the already existing HTML template
    return templates.TemplateResponse(
        request=request,
        name="order_success.html", # This is your full-page template
        context={
            "items": template_items,
            "grand_total": grand_total,
            "location_label": order.location
        }
    )

@router.post("/remove-from-cart/{product_id}")
async def remove_from_cart(
    product_id: int,
    request: Request,
    db: Session = Depends(get_session),
    extras: list[int] = Form(default=[])
):
    extras_sorted = sorted(extras)

    for i, item in enumerate(cart):
        if item["id"] == product_id and sorted(item.get("extras", [])) == extras_sorted:
            cart.pop(i)
            break

    return await show_cart(request, db)


@router.post("/increase-cart-item/{product_id}")
async def increase_cart_item(
    product_id: int,
    request: Request,
    db: Session = Depends(get_session),
    extras: list[int] = Form(default=[])
):
    extras_sorted = sorted(extras)

    for item in cart:
        if item["id"] == product_id and sorted(item.get("extras", [])) == extras_sorted:
            item["qty"] += 1
            break

    return await show_cart(request, db)


@router.post("/decrease-cart-item/{product_id}")
async def decrease_cart_item(
    product_id: int,
    request: Request,
    db: Session = Depends(get_session),
    extras: list[int] = Form(default=[])
):
    extras_sorted = sorted(extras)

    for i, item in enumerate(cart):
        if item["id"] == product_id and sorted(item.get("extras", [])) == extras_sorted:
            item["qty"] -= 1
            if item["qty"] <= 0:
                cart.pop(i)
            break

    return await show_cart(request, db)
