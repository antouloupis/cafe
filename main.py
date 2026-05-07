from fastapi import FastAPI
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

# Absolute imports (assuming main.py is in the root next to these files)
from database import init_db, engine
from models import AdminUser, Order
from utils import hash_password
from routers import admin, menu
from sqlmodel import Session, select, delete

# --- 1. The Cleanup Logic ---
def delete_old_orders():
    with Session(engine) as db:
        # Change to days=7 for production
        threshold = datetime.now(timezone.utc) - timedelta(days=7)
        statement = delete(Order).where(Order.created_at < threshold)
        result = db.exec(statement)
        db.commit()
        if result.rowcount > 0:
            print(f"🧹 Cleaned up {result.rowcount} old orders.")

async def periodic_cleanup():
    while True:
        try:
            await asyncio.to_thread(delete_old_orders)
        except Exception as e:
            print(f"Error during cleanup: {e}")
        # Run every hour (3600 seconds). Change to 10 for quick testing.
        await asyncio.sleep(10) 

# --- 2. The Lifespan Manager (Replaces @app.on_event) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    init_db()
    
    with Session(engine) as session:
        existing_admin = session.exec(select(AdminUser).where(AdminUser.username == "admin")).first()
        if not existing_admin:
            env_pass = os.getenv("ADMIN_PASSWORD")
            if env_pass:
                print("--- FIRST RUN: Creating Admin from .env ---")
                new_admin = AdminUser(hashed_password=hash_password(env_pass))
                session.add(new_admin)
                session.commit()
            else:
                print("--- WARNING: No Admin and no .env password found! ---")

    # Start the background cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    # --- SERVER IS RUNNING ---
    yield 
    
    # --- SHUTDOWN LOGIC ---
    # When the server is stopped, cancel the background loop cleanly
    cleanup_task.cancel()

# --- 3. App Initialization ---
app = FastAPI(lifespan=lifespan)

# Plug in the separate files
app.include_router(admin.router)
app.include_router(menu.router)