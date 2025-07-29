from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import Base, engine, get_db
from auth import router as auth_router
from routers import booking, user
from models import User, Booking
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/test-db")
def test_db(db: Session = Depends(get_db)):
    return {"status": "Connected to PostgreSQL"}

app.include_router(auth_router)
app.include_router(user.router)
app.include_router(booking.router)
