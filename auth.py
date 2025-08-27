from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import JWTError, jwt, ExpiredSignatureError
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, Request, status

from models import User
from database import get_db



# Load .env for local or production (Render)
load_dotenv("/etc/secrets/.env") if os.path.exists("/etc/secrets/.env") else load_dotenv()

# Password hashing config
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# JWT Config
SECRET_KEY = os.getenv("SECRET_KEY", "your_default_dev_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10"))

# Create access token
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Decode token (optional, not used directly in route)
def decode_access_token(token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload, None
    except ExpiredSignatureError:
        return None, "expired"
    except JWTError:
        return None, "invalid"


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return user
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

