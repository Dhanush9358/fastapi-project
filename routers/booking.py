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
    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]
    return templates.TemplateResponse("book.html", {
        "request": request,
        "room_map": room_map,
        "msg": ""
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
    try:
        booking_date = date.fromisoformat(date_str)
        start_datetime = datetime.combine(booking_date, time.fromisoformat(start_time))
        end_datetime = datetime.combine(booking_date, time.fromisoformat(end_time))

        if end_datetime <= start_datetime:
            return templates.TemplateResponse("book.html", {
                "request": request,
                "message": "❌ End time must be after start time"
            })

        # Check for overlapping booking
        overlapping = db.query(Booking).filter(
            Booking.date == booking_date,
            Booking.room_id == 1,  # Room 1 (or loop through available rooms)
            Booking.start_time < end_datetime,
            Booking.end_time > start_datetime
        ).first()

        if overlapping:
            return templates.TemplateResponse("book.html", {
                "request": request,
                "message": "❌ Room is not available at the selected time"
            })

        # Book room
        new_booking = Booking(
            name=name,
            user_id=current_user.id,
            room_id=1,
            date=booking_date,
            start_time=start_datetime,
            end_time=end_datetime
        )
        db.add(new_booking)
        db.commit()

        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "✅ Room booked successfully!"
        })
    except Exception as e:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": f"❌ Error occurred: {str(e)}"
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
