# routers/booking.py
from fastapi import APIRouter, Request, Form, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, time, timedelta
from typing import Optional

from database import get_db
from models import Booking, User
from auth import get_current_user
from schemas import UpdateBooking

router = APIRouter()
templates = Jinja2Templates(directory="templates")

ROOMS = list(range(1, 11))

# ----------------- helpers -----------------
def _parse_date(s: str) -> date:
    if isinstance(s, date):
        return s
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid date format")

def _parse_time(s: str) -> time:
    if isinstance(s, time):
        return s
    s = str(s).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise ValueError("Invalid time format")

def _find_available_room(db: Session, booking_date: date, start: time, end: time, exclude_booking_id: Optional[int] = None) -> Optional[int]:
    for rn in ROOMS:
        q = db.query(Booking).filter(
            Booking.date == booking_date,
            Booking.room_number == rn
        )
        if exclude_booking_id:
            q = q.filter(Booking.id != exclude_booking_id)
        # conflict when existing.start < end and existing.end > start
        conflict = q.filter(Booking.start_time < end, Booking.end_time > start).first()
        if not conflict:
            return rn
    return None

def _room_map(db: Session):
    bookings = db.query(Booking).join(User).all()
    return [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]

# ----------------- Routers -----------------
# ----------------- book -----------------
@router.get("/book", response_class=HTMLResponse)
def book_form(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = date.today().isoformat()
    return templates.TemplateResponse("book.html", {
        "request": request,
        "room_map": _room_map(db),
        "message": "",
        "current_date": today
    })

@router.post("/book", response_class=HTMLResponse)
def book_room(request: Request,
              name: str = Form(...),
              date_str: str = Form(...),
              start_time: str = Form(...),
              end_time: str = Form(...),
              db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    today = date.today()
    try:
        booking_date = _parse_date(date_str)
        start = _parse_time(start_time)
        end = _parse_time(end_time)
    except ValueError as e:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": str(e),
            "current_date": today.isoformat(),
            "room_map": _room_map(db)
        })

    booking_start_dt = datetime.combine(booking_date, start)
    if booking_date < today or booking_start_dt <= datetime.now() + timedelta(minutes=1):
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "Cannot book for a past date/time.",
            "current_date": today.isoformat(),
            "room_map": _room_map(db)
        })

    if end <= start:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "End time must be after start time.",
            "current_date": today.isoformat(),
            "room_map": _room_map(db)
        })

    available_room = _find_available_room(db, booking_date, start, end)
    if not available_room:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "No rooms available for the selected time.",
            "current_date": today.isoformat(),
            "room_map": _room_map(db)
        })

    new_booking = Booking(
        name=name,
        user_id=current_user.id,
        room_number=available_room,
        date=booking_date,
        start_time=start,
        end_time=end
    )
    db.add(new_booking)
    db.commit()
    return templates.TemplateResponse("book.html", {
        "request": request,
        "message": f"✅ Room {available_room} successfully booked!",
        "current_date": today.isoformat(),
        "room_map": _room_map(db)
    })

# ----------------- history -----------------
@router.get("/history")
def booking_history(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None)
):
    query = db.query(Booking).filter(Booking.user_id == current_user.id)
    warning_message = None

    if (start_time or end_time) and not date:
        warning_message = "Please select a date when filtering by time."
    elif date:
        try:
            filter_date = _parse_date(date)
            query = query.filter(Booking.date == filter_date)

            if start_time:
                query = query.filter(Booking.start_time >= _parse_time(start_time))
            if end_time:
                query = query.filter(Booking.end_time <= _parse_time(end_time))
        except ValueError:
            warning_message = "Invalid date or time format."

    bookings = query.order_by(Booking.date.desc(), Booking.start_time.desc()).all()
    now = datetime.now()

    booking_list = [
        {
            "id": b.id,
            "room_number": b.room_number,
            "date": b.date.strftime("%Y-%m-%d"),
            "start_time": b.start_time.strftime("%H:%M"),
            "end_time": b.end_time.strftime("%H:%M"),
            "is_expired": now >= datetime.combine(b.date, b.end_time),
            "can_edit": now < datetime.combine(b.date, b.end_time)
        }
        for b in bookings
    ]

    return templates.TemplateResponse("history.html", {
        "request": request,
        "bookings": booking_list,
        "warning_message": warning_message,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "current_date": date.today().strftime("%Y-%m-%d")
    })

# ----------------- Edit Booking -----------------
@router.get("/edit_booking/{booking_id}")
def edit_booking_form(booking_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == current_user.id).first()
    if not booking or booking.date < date.today():
        return RedirectResponse(url="/history")
    return templates.TemplateResponse("edit_booking.html", {"request": request, "booking": booking})

@router.post("/edit_booking/{booking_id}")
def edit_booking_submit(booking_id: int, request: Request,
                        new_date: str = Form(...), new_start: str = Form(...), new_end: str = Form(...),
                        db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == current_user.id).first()
    if not booking:
        return RedirectResponse(url="/history")

    try:
        new_date_obj = _parse_date(new_date)
        new_start_obj = _parse_time(new_start)
        new_end_obj = _parse_time(new_end)
    except ValueError as e:
        return templates.TemplateResponse("edit_booking.html", {"request": request, "booking": booking, "error": str(e)})

    new_start_dt = datetime.combine(new_date_obj, new_start_obj)
    if new_date_obj < date.today() or new_start_dt <= datetime.now() + timedelta(minutes=1):
        return templates.TemplateResponse("edit_booking.html", {"request": request, "booking": booking, "error": "Cannot set to a past or ongoing time."})
    if new_end_obj <= new_start_obj:
        return templates.TemplateResponse("edit_booking.html", {"request": request, "booking": booking, "error": "End time must be after start time."})

    available_room = _find_available_room(db, new_date_obj, new_start_obj, new_end_obj, exclude_booking_id=booking.id)
    if not available_room:
        return templates.TemplateResponse("edit_booking.html", {"request": request, "booking": booking, "error": "❌ No rooms available for the selected time."})

    booking.date = new_date_obj
    booking.start_time = new_start_obj
    booking.end_time = new_end_obj
    booking.room_number = available_room
    db.commit()
    return RedirectResponse(url="/history", status_code=303)

# ----------------- Update Booking -----------------
@router.put("/update-booking/{booking_id}")
async def update_booking(booking_id: int, details: UpdateBooking, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        selected_date = _parse_date(details.new_date)
        start_time_obj = _parse_time(details.new_start)
        end_time_obj = _parse_time(details.new_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format")

    if start_time_obj >= end_time_obj:
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    now = datetime.now()
    if selected_date < now.date() or (selected_date == now.date() and start_time_obj <= now.time()):
        raise HTTPException(status_code=400, detail="Cannot update booking to a past time")

    room_selected = details.room
    if not room_selected:
        raise HTTPException(status_code=400, detail="Room selection is required")

    # Conflict check (use parsed objects, not raw strings)
    conflict = db.query(Booking).filter(
        Booking.room_number == room_selected,
        Booking.date == selected_date,
        Booking.id != booking_id,
        Booking.start_time < end_time_obj,
        Booking.end_time > start_time_obj
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail=f"Room {room_selected} is already booked for this time")

    booking.date = selected_date
    booking.start_time = start_time_obj
    booking.end_time = end_time_obj
    booking.room_number = room_selected

    db.commit()
    db.refresh(booking)
    return {"message": "Booking updated successfully", "booking": {
        "id": booking.id,
        "room_number": booking.room_number,
        "date": booking.date.strftime("%Y-%m-%d"),
        "start_time": booking.start_time.strftime("%H:%M"),
        "end_time": booking.end_time.strftime("%H:%M")
    }}

# ----------------- Rooms Available -----------------
@router.post("/available-rooms/{booking_id}")
async def available_rooms(booking_id: int, details: UpdateBooking, db: Session = Depends(get_db)):
    try:
        date_obj = _parse_date(details.new_date)
        start = _parse_time(details.new_start)
        end = _parse_time(details.new_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format")

    if start >= end:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    booked = db.query(Booking.room_number).filter(
        Booking.date == date_obj,
        Booking.id != booking_id,
        Booking.start_time < end,
        Booking.end_time > start
    ).all()
    booked_rooms = {r[0] for r in booked}
    available = [r for r in ROOMS if r not in booked_rooms]
    return {"available_rooms": available}

# ----------------- Delete Booking -----------------
@router.delete("/delete-booking/{booking_id}")
async def delete_booking(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found or unauthorized")
    db.delete(booking)
    db.commit()
    return {"message": "Booking deleted successfully"}
