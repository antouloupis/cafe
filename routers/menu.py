from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session, select
from database import get_session
from models import Product
from utils import templates

router = APIRouter(tags=["Menu"])

cart = []

# 1️⃣ The Main Page: Renders the full menu
from collections import defaultdict

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_session)):
    products = db.exec(select(Product)).all()
    
    # Group products by category
    products_by_category = defaultdict(list)
    for product in products:
        products_by_category[product.category].append(product)

    return templates.TemplateResponse(
        request,
        "menu.html",
        {
            "request": request,
            "products_by_category": products_by_category,
            "title": "Coffee Menu",
            "cart": cart
        }
    )

@router.get("/product-options/{product_id}")
async def product_options(product_id: int, db: Session = Depends(get_session)):
    product = db.get(Product, product_id)
    if not product:
        return Response("<p>Product not found</p>", media_type="text/html")

    html = f"""
    <div class="space-y-5">
        <div class="flex items-start justify-between gap-4 border-b border-gray-200 pb-4">
            <div>
                <h3 class="text-2xl font-extrabold uppercase text-[#2f3517]">{product.name}</h3>
                <p class="text-gray-500 mt-1">Αρχική Τιμή: €{product.price:.2f}</p>
            </div>
            <button
                onclick="document.getElementById('modal').style.display='none'"
                class="text-2xl text-gray-500 hover:text-black"
                type="button">
                ✕
            </button>
        </div>
    """

    if product.options:
        html += """
        <div>
            <h4 class="text-sm font-bold uppercase tracking-[0.2em] text-gray-500 mb-3">Extras</h4>
            <div class="space-y-3">
        """
        for opt in product.options:
            html += f"""
                <label class="flex items-center justify-between border border-gray-200 bg-white px-4 py-3 cursor-pointer hover:bg-gray-50">
                    <div class="flex items-center gap-3">
                        <input type="checkbox" name="extras" value="{opt.id}" class="h-4 w-4">
                        <div>
                            <p class="font-semibold text-[#2f3517]">{opt.group_name}: {opt.value}</p>
                        </div>
                    </div>
                    <span class="font-bold text-[#2f3517]">+€{opt.extra_price:.2f}</span>
                </label>
            """
        html += "</div></div>"
    else:
        html += """
        <p class="text-gray-500 italic">No extras available</p>
        """

    html += f"""
        <button
            hx-post="/add-to-cart/{product.id}"
            hx-target="#modal-body"
            hx-swap="innerHTML"
            hx-include="input[name='extras']"
            class="w-full bg-[#556b2f] text-white py-3 px-4 font-bold uppercase tracking-wider hover:opacity-95 transition">
            Add to Order
        </button>
    </div>
    """

    return Response(content=html, media_type="text/html")



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
    <p class="text-lg font-bold text-[#2f3517] uppercase">Added to cart</p>
    <button
        type="button"
        onclick="document.getElementById('modal').style.display='none'"
        class="bg-[#556b2f] text-white px-5 py-3 font-bold uppercase tracking-wider">
        Close
    </button>
</div>
""",
media_type="text/html"
)


      

@router.get("/cart")
async def show_cart(request: Request, db: Session = Depends(get_session)):
    grand_total = 0.0

    html = """
    <div class="min-h-screen text-[#4b5320] bg-cover bg-center bg-fixed" style="background-image: url('/static/bg.jpg');">
      <div class="min-h-screen bg-[rgba(243,243,241,0.50)]">
        <div id="page" class="min-h-screen flex flex-col">

          <header class="bg-[#f3f3f1]">
            <div class="page-container py-8">
              <div class="flex items-center justify-center gap-4 md:gap-8">
                <img
                  src="/static/29taxlogonoback.png"
                  alt="29 Μ/Π ΤΑΞ Logo"
                  class="h-16 w-16 object-contain md:h-24 md:w-24"
                />

                <h1 class="main-title mb-0">
                  ΚΑΛΑΘΙ ΠΑΡΑΓΓΕΛΙΑΣ
                </h1>

                <img
                  src="/static/geslogonoback.png"
                  alt="ΓΕΣ Logo"
                  class="h-16 w-16 object-contain md:h-24 md:w-24"
                />
              </div>
            </div>
          </header>

          <main class="flex-1">
            <div class="page-container pt-6 pb-24 text-center">
    """

    if not cart:
        html += """
              <div class="max-w-2xl mx-auto bg-[#f8f8f6] border border-[#d6d6cc] shadow-sm p-8 text-center">
                <h2 class="text-2xl font-extrabold uppercase text-[#2f3517]">Το καλάθι είναι άδειο</h2>
                <p class="mt-3 text-gray-600">Πρόσθεσε προϊόντα για να συνεχίσεις την παραγγελία.</p>

                <button
                  type="button"
                  onclick="window.location='/'"
                  class="mt-6 bg-[#556b2f] text-white px-6 py-3 font-bold uppercase tracking-wider">
                  Επιστροφή στο Μενού
                </button>
              </div>
        """
    else:
        html += """
              <div class="max-w-5xl mx-auto space-y-6">
        """

        for item in cart:
            product = db.get(Product, item["id"])
            if not product:
                continue

            base_price = float(product.price)
            unit_price = base_price
            extras_html = ""
            extras_inputs = ""

            if "extras" in item and item["extras"]:
                extras_html += """
                <div class="mt-4 border-t border-[#d6d6cc] pt-4">
                  <p class="text-xs font-bold uppercase tracking-[0.2em] text-gray-500 mb-3">Επιλεγμένα Extras</p>
                  <div class="space-y-2">
                """

                for extra_id in item["extras"]:
                    extra = next((opt for opt in product.options if opt.id == extra_id), None)
                    if extra:
                        unit_price += float(extra.extra_price)
                        extras_html += f"""
                        <div class="flex items-center justify-between bg-white border border-[#d6d6cc] px-4 py-3 text-left">
                          <span class="font-semibold text-[#2f3517]">{extra.group_name}: {extra.value}</span>
                          <span class="font-bold text-[#2f3517]">+€{float(extra.extra_price):.2f}</span>
                        </div>
                        """
                        extras_inputs += f'<input type="hidden" name="extras" value="{extra.id}">'

                extras_html += """
                  </div>
                </div>
                """

            item_total = unit_price * item["qty"]
            grand_total += item_total

            html += f"""
                <div class="bg-[#f8f8f6] border border-[#d6d6cc] shadow-sm p-6 text-left">
                  <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-6">

                    <div class="flex-1">
                      <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                        <div>
                          <h2 class="text-2xl font-extrabold uppercase text-[#2f3517]">{product.name}</h2>
                          <p class="mt-2 text-gray-600">Αρχική Τιμή: €{base_price:.2f}</p>
                        </div>


<div class="text-left md:text-right">
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:10px;">

    <div style="display:flex;align-items:center;gap:8px;">
      <form
        hx-post="/decrease-cart-item/{product.id}"
        hx-target="#page"
        hx-swap="innerHTML"
        style="margin:0;"
      >
        {extras_inputs}
        <button
          type="submit"
          style="background:#e5e7eb;color:#111827;padding:8px 14px;border:1px solid #3f4f22;font-weight:700;cursor:pointer;width:44px;">
          −
        </button>
      </form>

      <div style="background:#a3b18a;color:#243010;padding:8px 16px;font-weight:700;border:1px solid #7f8f6a;width:140px;text-align:center;">
        Ποσότητα: {item['qty']}
      </div>

      <form
        hx-post="/increase-cart-item/{product.id}"
        hx-target="#page"
        hx-swap="innerHTML"
        style="margin:0;"
      >
        {extras_inputs}
        <button
          type="submit"
          style="background:#e5e7eb;color:#111827;padding:8px 14px;border:1px solid #3f4f22;font-weight:700;cursor:pointer;width:44px;">
          +
        </button>
      </form>
    </div>

    <form
      hx-post="/remove-from-cart/{product.id}"
      hx-target="#page"
      hx-swap="innerHTML"
      style="margin:0;width:244px;"
    >
      {extras_inputs}
      <button
        type="submit"
        style="background:#b91c1c;color:white;padding:10px 16px;border:1px solid #991b1b;font-weight:700;text-transform:uppercase;cursor:pointer;width:100%;">
        Διαγραφή
      </button>
    </form>

  </div>
</div>
                        

   
                        

                      </div>

                      {extras_html}
                    </div>

                    <div class="min-w-[160px] bg-white border border-[#d6d6cc] p-4 text-center">
                      <p class="text-xs uppercase tracking-[0.2em] text-gray-500">Σύνολο Είδους</p>
                      <p class="mt-2 text-2xl font-extrabold text-[#2f3517]">€{item_total:.2f}</p>
                    </div>
                  </div>
                </div>
            """

        html += f"""
              </div>

              <div class="max-w-5xl mx-auto mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">

                <div class="bg-[#f8f8f6] border border-[#d6d6cc] shadow-sm p-6 text-left">
                  <label for="delivery-location" class="block text-sm font-bold uppercase tracking-[0.2em] text-[#2f3517] mb-3">
                    Επιλογή Τοποθεσίας Παράδοσης
                  </label>

                  <select
                    id="delivery-location"
                    name="location"
                    class="w-full border border-[#d6d6cc] bg-white px-4 py-3 text-[#2f3517] font-semibold">
                    <option value="1">1ο Γραφείο</option>
                    <option value="2">2ο Γραφείο</option>
                    <option value="3">3ο Γραφείο</option>
                    <option value="4">Γραφείο Έρευνας Πληροφορικής</option>
                    <option value="5">Υπασπιστήριο</option>
                    <option value="6">Επιτελάρχης</option>
                    <option value="7">Συντονιστής</option>
                    <option value="8">Υποδιοικητής</option>
                  </select>
                </div>

                <div class="bg-[#556b2f] text-white shadow-lg p-6 text-center">
                  <p class="text-sm uppercase tracking-[0.2em] text-white/80">Γενικό Σύνολο</p>
                  <p class="mt-3 text-4xl font-extrabold">€{grand_total:.2f}</p>

                  <div class="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
                    <button
                      class="bg-white text-[#556b2f] px-6 py-3 font-bold uppercase tracking-wider"
                      hx-post="/place-order"
                      hx-target="#page"
                      hx-swap="innerHTML"
                      hx-include="select#delivery-location">
                      ✅ Καταχώρηση Παραγγελίας
                    </button>

                    <button
                      type="button"
                      onclick="window.location='/'"
                      class="border border-white text-white px-6 py-3 font-bold uppercase tracking-wider">
                      Επιστροφή στο Μενού
                    </button>
                  </div>
                </div>
              </div>
        """

    html += """
            </div>
          </main>

          <footer class="bg-[#556b2f] text-white mt-12">
            <div class="footer-container">
              <p>29 Μ/Π ΤΑΞ 2026 ©</p>
              <div class="footer-right">
                <span>Created by</span>
                <span><b>Γραφείο Έρευνας Πληροφορικής</b></span>
                <span><b>Ραβανός Ευστάθιος & Τουλούπης Αντώνιος</b></span>
              </div>
            </div>
          </footer>

        </div>
      </div>
    </div>
    """

    return HTMLResponse(content=html)

#---------------------------------------------
from fastapi import HTTPException
from fastapi import Form
from models import Order, OrderItem, OrderItemOption

@router.post("/place-order")
async def place_order(
    location: str = Form(...),
    db: Session = Depends(get_session)
):
    if not cart:
        return HTMLResponse("<p>Your cart is empty 🥲</p>")

    # Κρατάμε snapshot για ανασκόπηση πριν αδειάσει το cart
    cart_snapshot = [item.copy() for item in cart]

    # 1️⃣ Create the main order
    order = Order(location=location)
    db.add(order)
    db.commit()
    db.refresh(order)

    grand_total = 0.0
    review_items_html = ""

    # 2️⃣ Add each item in the cart
    for item in cart_snapshot:
        product = db.get(Product, item["id"])
        if not product:
            continue

        base_price = float(product.price)
        unit_price = base_price

        order_item = OrderItem(
            name=product.name,
            price=base_price,
            order_id=order.id
        )
        db.add(order_item)
        db.commit()
        db.refresh(order_item)

        extras_html = ""

        # 3️⃣ Add selected extras for this item
        if "extras" in item and item["extras"]:
            extras_html += """
            <div class="mt-3 border-t border-[#d6d6cc] pt-3">
              <p class="text-xs font-bold uppercase tracking-[0.2em] text-gray-500 mb-2">Extras</p>
              <div class="space-y-2">
            """

            for extra_id in item["extras"]:
                extra = next((opt for opt in product.options if opt.id == extra_id), None)
                if extra:
                    unit_price += float(extra.extra_price)

                    order_item_option = OrderItemOption(
                        order_item_id=order_item.id,
                        group_name=extra.group_name,
                        value=extra.value,
                        extra_cost=extra.extra_price
                    )
                    db.add(order_item_option)
                    db.commit()

                    extras_html += f"""
                    <div class="flex items-center justify-between bg-white border border-[#d6d6cc] px-3 py-2">
                      <span class="font-semibold text-[#2f3517]">{extra.group_name}: {extra.value}</span>
                      <span class="font-bold text-[#2f3517]">+€{float(extra.extra_price):.2f}</span>
                    </div>
                    """

            extras_html += """
              </div>
            </div>
            """

        item_total = unit_price * item["qty"]
        grand_total += item_total

        review_items_html += f"""
        <div class="bg-white border border-[#d6d6cc] p-4 text-left">
          <div class="flex items-start justify-between gap-4">
            <div>
              <h3 class="text-xl font-extrabold uppercase text-[#2f3517]">{product.name}</h3>
              <p class="mt-1 text-gray-600">Αρχική Τιμή: €{base_price:.2f}</p>
              <p class="mt-1 text-gray-600">Ποσότητα: <b>{item['qty']}</b></p>
            </div>

            <div class="text-right min-w-[120px]">
              <p class="text-xs uppercase tracking-[0.2em] text-gray-500">Σύνολο</p>
              <p class="text-xl font-extrabold text-[#2f3517]">€{item_total:.2f}</p>
            </div>
          </div>

          {extras_html}
        </div>
        """

    # 4️⃣ Clear the cart after order is placed
    cart.clear()

    location_map = {
        "1": "1ο Γραφείο",
        "2": "2ο Γραφείο",
        "3": "3ο Γραφείο",
        "4": "Γραφείο Έρευνας Πληροφορικής",
        "5": "Υπασπιστήριο",
        "6": "Επιτελάρχης",
        "7": "Συντονιστής",
        "8": "Υποδιοικητής",
    }
    location_label = location_map.get(location, location)

    # 5️⃣ Return confirmation + review panel
    return HTMLResponse(f"""
<div class="min-h-screen text-[#4b5320] bg-cover bg-center bg-fixed" style="background-image: url('/static/bg.jpg');">
  <div class="min-h-screen bg-[rgba(243,243,241,0.50)]">
    <div id="page" class="min-h-screen flex flex-col">

      <header class="bg-[#f3f3f1]">
        <div class="page-container py-8">
          <div class="flex items-center justify-center gap-4 md:gap-8">
            <img
              src="/static/29taxlogonoback.png"
              alt="29 Μ/Π ΤΑΞ Logo"
              class="h-16 w-16 object-contain md:h-24 md:w-24"
            />

            <h1 class="main-title mb-0">
              ΤΕΛΟΣ ΠΑΡΑΓΓΕΛΙΑΣ
            </h1>

            <img
              src="/static/geslogonoback.png"
              alt="ΓΕΣ Logo"
              class="h-16 w-16 object-contain md:h-24 md:w-24"
            />
          </div>
        </div>
      </header>

      <main class="flex-1">
        <div class="page-container pt-10 pb-24">
          <div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-stretch">

            <!-- LEFT: confirmation -->
            <div class="bg-[#f8f8f6] border border-[#d6d6cc] shadow-sm p-10 h-full flex flex-col text-center">
              <div class="text-5xl mb-4">✅</div>

              <h2 class="text-3xl font-extrabold uppercase text-[#2f3517]">
                Η παραγγελία σας καταχωρήθηκε επιτυχώς.
              </h2>

              <p class="mt-4 text-gray-600 font-semibold uppercase tracking-wider">
                Αναμονή Παραγγελίας
              </p>

              <div style="margin-top:24px;">
                <div style="font-size:14px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#556b2f;margin-bottom:10px;">
                  Προετοιμασία / Παράδοση
                </div>

                <div style="
                  width:100%;
                  max-width:420px;
                  height:18px;
                  margin:0 auto;
                  background:#dfe6d3;
                  border:1px solid #b7c3a3;
                  border-radius:999px;
                  overflow:hidden;
                  box-shadow: inset 0 1px 2px rgba(0,0,0,0.08);
                ">
                  <div style="
                    height:100%;
                    width:35%;
                    background:linear-gradient(90deg, #556b2f, #8aa06a, #556b2f);
                    background-size:200% 100%;
                    border-radius:999px;
                    animation: loadingBar 1.6s ease-in-out infinite;
                  "></div>
                </div>

                <div style="margin-top:10px;color:#6b7280;font-size:14px;">
                  Η παραγγελία σας δρομολογείται...
                </div>
              </div>

              <div style="
                margin-top:34px;
                position:relative;
                width:100%;
                max-width:520px;
                height:120px;
                margin-left:auto;
                margin-right:auto;
                overflow:hidden;
                border-top:1px dashed #b8b8ae;
                border-bottom:1px dashed #b8b8ae;
                background:linear-gradient(to bottom, rgba(255,255,255,0.65), rgba(235,238,228,0.65));
              ">
                <div style="
                  position:absolute;
                  left:0;
                  right:0;
                  bottom:18px;
                  height:4px;
                  background:#7d8f61;
                "></div>

                <div style="
                  position:absolute;
                  left:-110px;
                  bottom:22px;
                  animation: marchAcross 8s linear infinite;
                ">
                  <div style="position:relative; width:90px; height:72px;">
                    <img
                      src="/static/Soldier2.png"
                      alt="Soldier delivery"
                      style="
                        height:68px;
                        width:auto;
                        object-fit:contain;
                        filter: drop-shadow(0 4px 6px rgba(0,0,0,0.18));
                        animation: soldierBounce 0.45s ease-in-out infinite alternate;
                      "
                    />

                    <div style="
                      position:absolute;
                      right:-10px;
                      top:22px;
                      background:#556b2f;
                      color:white;
                      font-size:10px;
                      font-weight:700;
                      padding:5px 8px;
                      border-radius:6px;
                      border:1px solid #3f4f22;
                      animation: boxBounce 0.45s ease-in-out infinite alternate;
                    ">
                      ☕ DELIVERY
                    </div>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onclick="window.location='/'"
                class="mt-8 bg-[#556b2f] text-white px-6 py-3 font-bold uppercase tracking-wider">
                Επιστροφή στο Μενού
              </button>
            </div>

            <!-- RIGHT: order review -->
            <div class="bg-[#f8f8f6] border border-[#d6d6cc] shadow-sm p-10 h-full flex flex-col">
              <h2 class="text-2xl font-extrabold uppercase text-[#2f3517] text-center">
                Ανασκόπηση Παραγγελίας
              </h2>

              <div class="mt-6 space-y-4" flex-1>
                {review_items_html}
              </div>

              <div class="mt-6 grid grid-cols-1 gap-4">
                <div class="bg-white border border-[#d6d6cc] p-4">
                  <p class="text-xs uppercase tracking-[0.2em] text-gray-500">Τοποθεσία Παράδοσης</p>
                  <p class="mt-2 text-lg font-bold text-[#2f3517]">{location_label}</p>
                </div>

                <div class="bg-[#556b2f] text-white p-5 text-center">
                  <p class="text-xs uppercase tracking-[0.2em] text-white/80">Γενικό Σύνολο</p>
                  <p class="mt-2 text-3xl font-extrabold">€{grand_total:.2f}</p>
                </div>
              </div>
            </div>

          </div>
        </div>
      </main>

      <footer class="bg-[#556b2f] text-white mt-12">
        <div class="footer-container">
          <p>29 Μ/Π ΤΑΞ 2026 ©</p>
          <div class="footer-right">
            <span>Created by</span>
            <span><b>Γραφείο Έρευνας Πληροφορικής</b></span>
            <span><b>Ραβανός Ευστάθιος & Τουλούπης Αντώνιος</b></span>
          </div>
        </div>
      </footer>

    </div>
  </div>
</div>

<style>
@keyframes loadingBar {{
  0%   {{ transform: translateX(-120%); background-position: 0% 50%; }}
  50%  {{ transform: translateX(110%); background-position: 100% 50%; }}
  100% {{ transform: translateX(-120%); background-position: 0% 50%; }}
}}

@keyframes marchAcross {{
  0%   {{ transform: translateX(0); }}
  100% {{ transform: translateX(650px); }}
}}

@keyframes soldierBounce {{
  0%   {{ transform: translateY(0px) rotate(-1deg); }}
  100% {{ transform: translateY(-4px) rotate(1deg); }}
}}

@keyframes boxBounce {{
  0%   {{ transform: translateY(0px); }}
  100% {{ transform: translateY(-3px); }}
}}
</style>
""")


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
