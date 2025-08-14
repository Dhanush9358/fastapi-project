from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from models import User
from database import get_db
from auth import hash_password, verify_password, create_access_token, decode_access_token
from datetime import timedelta
from dotenv import load_dotenv
import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")

load_dotenv("/etc/secrets/.env") if os.path.exists("/etc/secrets/.env") else load_dotenv()

# Configure FastAPI-Mail
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "Room Booking App"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS=os.getenv("USE_CREDENTIALS", "True").lower() == "true",
    VALIDATE_CERTS=os.getenv("VALIDATE_CERTS", "True").lower() == "true"
)

# ------------------- Register -------------------
@router.get("/register")
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register_post(
    request: Request,
    username: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not email.endswith("@gmail.com"):
        return templates.TemplateResponse("register.html", {"request": request, "msg": "Email must end with @gmail.com"})

    if db.query(User).filter((User.username == username) | (User.email == email)).first():
        return templates.TemplateResponse("register.html", {"request": request, "msg": "Username or email already exists"})

    user = User(
        username=username,
        email=email,
        password=hash_password(password)
    )
    db.add(user)
    db.commit()
    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

# ------------------- Login -------------------
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
        return templates.TemplateResponse("login.html", {"request": request, "msg": "Invalid username or password"})

    token = create_access_token({"sub": user.username})
    response = RedirectResponse("/book", status_code=status.HTTP_302_FOUND)
    response.set_cookie("access_token", token, httponly=True)
    return response

# ------------------- Logout -------------------
@router.get("/logout")
def logout(request: Request):
    response = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response

# ------------------- Forgot Password / Username -------------------
@router.get("/forgot", response_class=HTMLResponse)
def forgot_get(request: Request):
    return templates.TemplateResponse("forgot.html", {"request": request})

@router.post("/forgot", response_class=HTMLResponse)
async def forgot_post(
    request: Request,
    email: EmailStr = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("forgot.html", {"request": request, "msg": "❌ Invalid email"})

    # Token valid for 15 minutes
    reset_token = create_access_token({"sub": user.username}, expires_delta=timedelta(minutes=15))
    reset_link = f"{request.base_url}reset-password?token={reset_token}"

    body = f"""
Hello User,

We received a request to recover your account credentials.

🧑 Username: {user.username}

🔑 To reset your password, click the link below:
{reset_link}

This link will expire in 15 minutes.

If you didn't request this, just ignore this email.
"""

    message = MessageSchema(
        subject="🔐 Your Account Recovery Details",
        recipients=[email],
        body=body,
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)

    return templates.TemplateResponse("forgot.html", {"request": request, "msg": "📧 Username and reset link sent to your email!"})


# ------------------- Password Reset via Token -------------------
@router.get("/reset-password", response_class = HTMLResponse)
def reset_password_form(request: Request, token: str):
    payload, error = decode_access_token(token)

    if error == "expired":
        return templates.TemplateResponse("link_expired.html", {"request":request})
    elif error == "invalid":
        return templates.TemplateResponse("link_expired.html", {"request":request})
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

@router.post("/reset-password")
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    payload, error = decode_access_token(token)

    if error == "expired":
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "msg": "Reset link has expired. Please request a new one."
        })
    elif error == "invalid":
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "msg": "Invalid reset link."
        })

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "msg": "User not found"
        })

    user.password = hash_password(new_password)
    db.commit()
    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
