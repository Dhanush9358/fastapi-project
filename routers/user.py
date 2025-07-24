from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from auth import hash_password, verify_password
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    secret: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if user:
        return templates.TemplateResponse("register.html", {"request": {}, "msg": "User already exists"})
    new_user = User(
        username=username,
        email=email,
        password=hash_password(password),
        secret=secret
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login_user(
    username: str = Form(...),
    password: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse("login.html", {"request": request, "msg": "Invalid credentials"})
    response = RedirectResponse(url="/book", status_code=status.HTTP_302_FOUND)
    response.set_cookie("user_id", str(user.id))
    return response

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_form(request: Request):
    return templates.TemplateResponse("forgot.html", {"request": request})

@router.post("/forgot-password")
def forgot_password(email: str = Form(...), secret: str = Form(...), request: Request = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if user and user.secret == secret:
        return templates.TemplateResponse("forgot.html", {"request": request, "username": user.username, "password": user.password})
    return templates.TemplateResponse("forgot.html", {"request": request, "msg": "Invalid recovery info"})