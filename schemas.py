from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    secret: str

class UserLogin(BaseModel):
    username: str
    password: str

class BookingCreate(BaseModel):
    date: str 
    start_time: str
    end_time: str
