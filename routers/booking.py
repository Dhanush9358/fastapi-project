from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Booking, User
from fastapi.templating import Jinja2Templates
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/book", response_class=HTMLResponse)
def book_form(request: Request, db: Session = Depends(get_db)):
    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]
    return templates.TemplateResponse("book.html", {
        "request": request,
        "room_map": room_map,
        "msg": ""
    })


@router.post("/book")
def book_room(
    name: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    try:
        # Validate date & time
        booking_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        if booking_datetime < datetime.now():
            msg = "⚠️ You cannot book room for a past date or time."
            raise ValueError(msg)

        # Get booked rooms for the requested time
        booked_rooms = db.query(Booking.room_number).filter(
            Booking.date == date,
            Booking.start_time < end_time,
            Booking.end_time > start_time
        ).all()

        booked = {room[0] for room in booked_rooms}
        available_rooms = [i for i in range(1, 11) if i not in booked]

        if not available_rooms:
            msg = "❌ No rooms available for the selected date/time."
            raise ValueError(msg)

        # Book the first available room
        new_booking = Booking(
            user_id=int(user_id),
            room_number=available_rooms[0],
            date=date,
            start_time=start_time,
            end_time=end_time,
            name=name
        )
        db.add(new_booking)
        db.commit()
        msg = f"✅ Room {available_rooms[0]} booked successfully!"

    except ValueError as e:
        msg = str(e)

    except Exception:
        msg = "❌ Something went wrong. Please try again later."

    # Load room map again
    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]

    return templates.TemplateResponse("book.html", {
        "request": request,
        "msg": msg,
        "room_map": room_map
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
