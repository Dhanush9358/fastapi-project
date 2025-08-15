from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, time, timedelta

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
    current_user: dict = Depends(get_current_user)
):
    search_date = request.query_params.get("search_date")
    search_start_time = request.query_params.get("search_start_time")
    search_end_time = request.query_params.get("search_end_time")

    query = db.query(Booking).filter(Booking.user_id == current_user.id)

    # Must include date for searching
    if search_date:
        query = query.filter(Booking.date == search_date)

        # Time range logic
        if search_start_time:
            try:
                start_t = datetime.strptime(search_start_time, "%H:%M").time()

                # If end time not given → set to 23:59
                if search_end_time:
                    end_t = datetime.strptime(search_end_time, "%H:%M").time()
                else:
                    end_t = time(23, 59)

                query = query.filter(
                    Booking.start_time <= end_t,
                    Booking.end_time >= start_t
                )
            except ValueError:
                pass
    else:
        # No date → return no results
        return templates.TemplateResponse(
            "history.html",
            {
                "request": request,
                "bookings": [],
                "current_date": datetime.now().date(),
                "search_date": "",
                "search_start_time": search_start_time or "",
                "search_end_time": search_end_time or ""
            }
        )

    # Fetch and process bookings
    bookings = query.order_by(Booking.date.desc(), Booking.start_time.desc()).all()

    # Add "is_past" dynamically based on current datetime
    now = datetime.now()
    processed_bookings = []
    for b in bookings:
        booking_end_datetime = datetime.combine(b.date, b.end_time)
        is_past = now >= booking_end_datetime
        processed_bookings.append({
            "id": b.id,
            "room_number": b.room_number,
            "date": b.date,
            "start_time": b.start_time,
            "end_time": b.end_time,
            "end_datetime_str": booking_end_datetime.isoformat(),
            "is_past": is_past
        })

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "bookings": processed_bookings,
            "current_date": datetime.now().date(),
            "search_date": search_date or "",
            "search_start_time": search_start_time or "",
            "search_end_time": search_end_time or ""
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
