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
    today = date.today().isoformat()
    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]
    return templates.TemplateResponse("book.html", {
        "request": request,
        "room_map": room_map,
        "message": "",
        "current_date": today
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
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    booking_date = date.fromisoformat(date)
    today = date.today()

    if booking_date < today:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ You cannot book a room for a past date.",
            "current_date": today.isoformat()
        })

    start = datetime.combine(booking_date, time.fromisoformat(start_time))
    end = datetime.combine(booking_date, time.fromisoformat(end_time))

    if end <= start:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ End time must be after start time.",
            "current_date": today.isoformat()
        })

    # Check room availability (1 to 10)
    available_room = None
    for room_id in range(1, 11):
        conflict = db.query(Booking).filter(
            Booking.date == booking_date,
            Booking.room_id == room_id,
            Booking.start_time < end,
            Booking.end_time > start
        ).first()
        if not conflict:
            available_room = room_id
            break

    if not available_room:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ No rooms available for the selected time.",
            "current_date": today.isoformat()
        })

    # Book the room
    new_booking = Booking(
        name=name,
        user_id=int(user_id),
        room_id=available_room,
        date=booking_date,
        start_time=start,
        end_time=end
    )
    db.add(new_booking)
    db.commit()

    return templates.TemplateResponse("book.html", {
        "request": request,
        "message": f"✅ Room {available_room} successfully booked!",
        "current_date": today.isoformat()
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

