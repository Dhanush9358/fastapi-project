from fastapi import APIRouter, Form, Request, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates
from models import User
from database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Utility Functions ---
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- Pages ---
@router.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/login")
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "msg": "Invalid username or password"
        })
    
    # You can add session logic here later
    response = RedirectResponse(url="/book", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="user_id", value=str(user.id))
    return response

@router.get("/register")
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    security_key: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "msg": "Username or Email already exists"
        })

    hashed_pw = hash_password(password)
    new_user = User(
        username=username,
        email=email,
        password=hashed_pw,
        security_key=security_key
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

# --- Forgot Page ---
@router.get("/forgot")
def forgot_get(request: Request):
    return templates.TemplateResponse("forgot.html", {"request": request})

@router.post("/forgot")
def forgot_post(
    request: Request,
    email: str = Form(...),
    secret: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        (User.email == email) & (User.security_key == secret)
    ).first()
    
    if user:
        return templates.TemplateResponse("forgot.html", {
            "request": request,
            "username": user.username,
            "password": user.password
        })
    else:
        return templates.TemplateResponse("forgot.html", {
            "request": request,
            "msg": "Invalid email or security key"
        })

@router.get("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("user_id")
    return response

