from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from database import get_session
from models import Product, ProductOption
from utils import templates

router = APIRouter(tags=["Menu"])

# 1. The Main HTML Page
@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_session)):
    products = db.exec(select(Product)).all()
    return templates.TemplateResponse(
        request=request,
        name="menu.html",
        context={"products": products} 
    )
