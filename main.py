from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import Base, engine
from routers import booking, user

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


app.include_router(user.router)
app.include_router(booking.router)
