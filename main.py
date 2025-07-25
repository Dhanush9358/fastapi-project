from fastapi import FastAPI, Request
from database import Base, engine
from routers import user, booking
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import auth


# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Root route
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Include routers
app.include_router(user.router)
app.include_router(booking.router)
app.include_router(auth.router)

