from fastapi import APIRouter, Request, Form, Depends, Response
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth import hash_password
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    security_key: str = Form(...),
    db: Session = Depends(get_db)
):
    hashed_pw = hash_password(password)
    new_user = User(username=username, email=email, password=hashed_pw, security_key=security_key)
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/logout")
def logout(response: Response):
    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie("user_id")
    return redirect