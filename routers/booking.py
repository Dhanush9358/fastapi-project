from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Booking, User
from fastapi.templating import Jinja2Templates
from datetime import datetime, date, time

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/book", response_class=HTMLResponse)
def book_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("book.html", {
        "request": request,
        "message": ""
    })

@router.post("/book", response_class=HTMLResponse)
def book_room(
    request: Request,
    name: str = Form(...),
    date_str: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    booking_date = date.fromisoformat(date_str)
    today = date.today()
    if booking_date < today:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ You cannot book a room for a past date."
        })

    start_datetime = datetime.combine(booking_date, time.fromisoformat(start_time))
    end_datetime = datetime.combine(booking_date, time.fromisoformat(end_time))

    if end_datetime <= start_datetime:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ End time must be after start time."
        })

    # Check for available room (1 to 10)
    available_room = None
    for room_id in range(1, 11):
        overlapping = db.query(Booking).filter(
            Booking.date == booking_date,
            Booking.room_id == room_id,
            Booking.start_time < end_datetime,
            Booking.end_time > start_datetime
        ).first()
        if not overlapping:
            available_room = room_id
            break

    if not available_room:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ No rooms available for the selected date and time."
        })

    new_booking = Booking(
        name=name,
        user_id=int(user_id),
        room_id=available_room,
        date=booking_date,
        start_time=start_datetime,
        end_time=end_datetime
    )
    db.add(new_booking)
    db.commit()

    return templates.TemplateResponse("book.html", {
        "request": request,
        "message": f"✅ Room {available_room} successfully booked."
    })

@router.get("/history", response_class=HTMLResponse)
def booking_history(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    bookings = db.query(Booking).filter(Booking.user_id == int(user_id)).all()
    return templates.TemplateResponse("history.html", {
        "request": request,
        "bookings": bookings
    })


# @router.get("/book", response_class=HTMLResponse)
# def book_form(request: Request, db: Session = Depends(get_db)):
#     bookings = db.query(Booking).join(User).all()
#     room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]
#     return templates.TemplateResponse("book.html", {
#         "request": request,
#         "room_map": room_map,
#         "msg": ""
#     })

