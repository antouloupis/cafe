from fastapi import FastAPI
from sqlmodel import Session, select
import os

from database import init_db, engine
from models import AdminUser
from utils import hash_password

# Import your new routers
from routers import admin, menu

app = FastAPI()

# Plug in the separate files
app.include_router(admin.router)
app.include_router(menu.router)

@app.on_event("startup")
def on_startup():
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