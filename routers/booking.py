from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, time, timedelta
from typing import Optional

from database import get_db
from models import Booking, User
from auth import get_current_user


router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/book", response_class=HTMLResponse)
def book_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    booking_date = date.fromisoformat(date_str)
    start = time.fromisoformat(start_time)
    end = time.fromisoformat(end_time)
    booking_start_datetime = datetime.combine(booking_date, start)

    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]

    if booking_date < today:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ You cannot book a room for a past date.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })

    if booking_start_datetime <= datetime.now() + timedelta(minutes=1):
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ Cannot book for a past date/time.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })

    if end <= start:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ End time must be after start time.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })

    available_room = None
    for room_number in range(1, 11):
        conflict = db.query(Booking).filter(
            Booking.date == booking_date,
            Booking.room_number == room_number,
            Booking.start_time < end,
            Booking.end_time > start
        ).first()
        if not conflict:
            available_room = room_number
            break

    if not available_room:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ No rooms available for the selected time.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })

    new_booking = Booking(
        name=name,
        user_id=current_user.id,  # ✅ use JWT-authenticated user
        room_number=available_room,
        date=booking_date,
        start_time=start,
        end_time=end
    )
    db.add(new_booking)
    db.commit()

    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]

    return templates.TemplateResponse("book.html", {
        "request": request,
        "message": f"✅ Room {available_room} successfully booked!",
        "current_date": today.isoformat(),
        "room_map": room_map
    })

@router.get("/history")
def booking_history(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date: Optional[str] = Query(None),
    time: Optional[str] = Query(None)
):
    # Check for warning: if time is given without date
    warning_message = None
    if time and not date:
        warning_message = "⚠️ Please select a date when filtering by time."

    # Base query
    query = db.query(Booking).filter(Booking.user_id == current_user.id)

    # Apply filters only if no warning
    if not warning_message:
        if date:
            try:
                filter_date = datetime.strptime(date, "%Y-%m-%d").date()
                query = query.filter(Booking.date == filter_date)
            except ValueError:
                warning_message = "Invalid date format."

        if date and time:
            try:
                filter_time = datetime.strptime(time, "%H:%M").time()
                query = query.filter(Booking.start_time >= filter_time)
            except ValueError:
                warning_message = "Invalid time format."

    bookings = query.order_by(Booking.date.desc(), Booking.start_time.desc()).all()

    # Prepare safe data (no recursion issue)
    now = datetime.now()
    booking_list = []
    for booking in bookings:
        booking_datetime = datetime.combine(booking.date, booking.end_time)

        booking_list.append({
            "id": booking.id,
            "room_id": booking.room_id,
            "date": booking.date.strftime("%Y-%m-%d"),
            "start_time": booking.start_time.strftime("%H:%M"),
            "end_time": booking.end_time.strftime("%H:%M"),
            "is_expired": now >= booking_datetime,
            "can_edit": now < booking_datetime
        })

    # Render template
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "bookings": booking_list,
            "warning_message": warning_message
        }
    )

@router.get("/edit_booking/{booking_id}")
def edit_booking_form(booking_id: int, request: Request, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return RedirectResponse(url="/history")
    
    # Optional: Only allow editing future bookings
    if booking.date < date.today():
        return RedirectResponse(url="/history")
    
    return templates.TemplateResponse("edit_booking.html", {
        "request": request,
        "booking": booking
    })

@router.post("/edit_booking/{booking_id}")
def edit_booking_submit(
    booking_id: int,
    request: Request,
    new_date: str = Form(...),
    new_start: str = Form(...),
    new_end: str = Form(...),
    db: Session = Depends(get_db)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return RedirectResponse(url="/history")
    
    # Convert strings to datetime objects
    new_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
    new_start_obj = datetime.strptime(new_start, "%H:%M").time()
    new_end_obj = datetime.strptime(new_end, "%H:%M").time()

    # Check for availability: any booking with same room and overlapping time
    overlapping = db.query(Booking).filter(
        Booking.room_number == booking.room_number,
        Booking.date == new_date_obj,
        Booking.id != booking.id,  # exclude current booking
        Booking.start_time < new_end_obj,
        Booking.end_time > new_start_obj
    ).first()

    if overlapping:
        return templates.TemplateResponse("edit_booking.html", {
            "request": request,
            "booking": booking,
            "error": "Selected time slot is not available."
        })

    # Update booking
    booking.date = new_date_obj
    booking.start_time = new_start_obj
    booking.end_time = new_end_obj
    db.commit()

    return RedirectResponse(url="/history", status_code=303)
