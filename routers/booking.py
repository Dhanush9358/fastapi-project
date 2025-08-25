from fastapi import APIRouter, Request, Form, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, and_, or_
from datetime import datetime, date, time, timedelta
from typing import Optional

from database import get_db
from models import Booking, User
from auth import get_current_user
from schemas import UpdateBooking
import models


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
            "message": "You cannot book a room for a past date.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })

    if booking_start_datetime <= datetime.now() + timedelta(minutes=1):
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "Cannot book for a past date/time.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })

    if end <= start:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "End time must be after start time.",
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
            "message": "No rooms available for the selected time.",
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
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None)
):
    # Check for warning: if time is given without date
    warning_message = None
    if (start_time or end_time) and not date:
        warning_message = "Please select a date when filtering by time."

    # Base query
    query = db.query(Booking).filter(Booking.user_id == current_user.id)

    # Apply filters only if there's no warning
    if not warning_message:
        if date:
            try:
                filter_date = datetime.strptime(date, "%Y-%m-%d").date()
                query = query.filter(Booking.date == filter_date)
            except ValueError:
                warning_message = "Invalid date format."

        if date and start_time:
            try:
                filter_start = datetime.strptime(start_time, "%H:%M").time()
                query = query.filter(Booking.start_time >= filter_start)
            except ValueError:
                warning_message = "Invalid start time format."

        if date and end_time:
            try:
                filter_end = datetime.strptime(end_time, "%H:%M").time()
                query = query.filter(Booking.end_time <= filter_end)
            except ValueError:
                warning_message = "Invalid end time format."

    bookings = query.order_by(Booking.date.desc(), Booking.start_time.desc()).all()

    # Mark expired bookings
    now = datetime.now()
    today_str = datetime.today().date().strftime("%Y-%m-%d")  # Current date for template
    booking_list = []
    for booking in bookings:
        booking_datetime = datetime.combine(booking.date, booking.end_time)

        booking_list.append({
            "id": booking.id,
            "room_number": booking.room_number,
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
            "warning_message": warning_message,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "current_date": today_str  # pass today to template
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ Ensure user is authenticated
):
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == current_user.id).first()
    if not booking:
        return RedirectResponse(url="/history")

    today = date.today()
    new_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
    new_start_obj = datetime.strptime(new_start, "%H:%M").time()
    new_end_obj = datetime.strptime(new_end, "%H:%M").time()

    # ✅ Combine new date and start time to check if in past
    new_start_datetime = datetime.combine(new_date_obj, new_start_obj)

    # ✅ Validation 1: Cannot set to past date
    if new_date_obj < today:
        return templates.TemplateResponse("edit_booking.html", {
            "request": request,
            "booking": booking,
            "error": "You cannot set a past date"
        })

    # ✅ Validation 2: Cannot set to time already passed (within today)
    if new_start_datetime <= datetime.now() + timedelta(minutes=1):
        return templates.TemplateResponse("edit_booking.html", {
            "request": request,
            "booking": booking,
            "error": "Cannot set to a past or ongoing time."
        })

    # ✅ Validation 3: End time must be after start time
    if new_end_obj <= new_start_obj:
        return templates.TemplateResponse("edit_booking.html", {
            "request": request,
            "booking": booking,
            "error": "End time must be after start time."
        })

    # ✅ Find an available room (same logic as /book)
    available_room = None
    for room_number in range(1, 11):
        conflict = db.query(Booking).filter(
            Booking.date == new_date_obj,
            Booking.room_number == room_number,
            Booking.id != booking.id,  # exclude current booking
            Booking.start_time < new_end_obj,
            Booking.end_time > new_start_obj
        ).first()
        if not conflict:
            available_room = room_number
            break

    if not available_room:
        return templates.TemplateResponse("edit_booking.html", {
            "request": request,
            "booking": booking,
            "error": "❌ No rooms available for the selected time."
        })

    # ✅ Update booking details
    booking.date = new_date_obj
    booking.start_time = new_start_obj
    booking.end_time = new_end_obj
    booking.room_number = available_room
    db.commit()

    return RedirectResponse(url="/history", status_code=303)

@router.put("/update-booking/{booking_id}")
async def update_booking(
    booking_id: int,
    details: UpdateBooking,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.user_id == user.id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # ✅ Extract and validate inputs
    new_date = details.new_date.strip()
    new_start = details.new_start.strip()
    new_end = details.new_end.strip()
    new_room = getattr(details, "room", None)

    if not new_room:
        raise HTTPException(status_code=400, detail="Room selection is required")

    try:
        selected_date = datetime.strptime(new_date, "%Y-%m-%d").date()
        start_time_obj = datetime.strptime(new_start, "%H:%M").time()
        end_time_obj = datetime.strptime(new_end, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format")

    if start_time_obj >= end_time_obj:
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    now = datetime.now()
    if selected_date < now.date() or (selected_date == now.date() and start_time_obj <= now.time()):
        raise HTTPException(status_code=400, detail="Cannot update booking to a past time")

    # ✅ Conflict check for selected room
    conflict = db.query(Booking).filter(
        Booking.room_number == new_room,
        Booking.date == new_date,
        Booking.id != booking_id,
        (Booking.start_time < new_end) & (Booking.end_time > new_start)
    ).first()

    if conflict:
        raise HTTPException(status_code=400, detail=f"Room {new_room} is already booked for this time")

    # ✅ Update booking
    booking.date = new_date
    booking.start_time = new_start
    booking.end_time = new_end
    booking.room_number = new_room

    db.commit()
    db.refresh(booking)

    return {
        "message": "Booking updated successfully",
        "booking": {
            "id": booking.id,
            "room_number": booking.room_number,
            "date": booking.date,
            "start_time": booking.start_time,
            "end_time": booking.end_time
        }
    }


@router.post("/available-rooms/{booking_id}")
async def available_rooms(booking_id: int, details: UpdateBooking, db: Session = Depends(get_db)):
    date_str = details.new_date.strip()
    start = details.new_start.strip()
    end = details.new_end.strip()

    # Validate input
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        datetime.strptime(start, "%H:%M")
        datetime.strptime(end, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format")

    # Find booked rooms for that time slot (excluding current booking)
    booked_rooms = db.query(Booking.room_number).filter(
        Booking.date == date_str,
        Booking.id != booking_id,
        (Booking.start_time < end) & (Booking.end_time > start)
    ).all()

    booked_rooms = [room[0] for room in booked_rooms]

    # Fetch all rooms and exclude booked ones
    all_rooms = [101, 102, 103, 104]  # Replace with DB query if rooms stored in DB
    available_rooms = [r for r in all_rooms if r not in booked_rooms]

    return {"available_rooms": available_rooms}


@router.delete("/delete-booking/{booking_id}")
async def delete_booking(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found or unauthorized")

    db.delete(booking)
    db.commit()
    return {"message": "Booking deleted successfully"}

