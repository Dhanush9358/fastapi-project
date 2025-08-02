from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    secret: str

class UserLogin(BaseModel):
    username: str
    password: str

class BookingCreate(BaseModel):
    date: str 
    start_time: str
    end_time: str

# ✅ For password reset email
class EmailRequest(BaseModel):
    email: EmailStr

# ✅ For submitting new password
class PasswordReset(BaseModel):
    token: str
    new_password: str
