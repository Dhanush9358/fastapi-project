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

    booking_date = date.fromisoformat(date_str)
    today = date.today()
    
    now = datetime.now()

    # Convert string times to time objects
    start = time.fromisoformat(start_time)
    end = time.fromisoformat(end_time)

    booking_start_datetime = datetime.combine(booking_date, start)
    # booking_end_datetime = datetime.combine(booking_date, end)

    # get latest booking map
    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]

    if booking_date < today:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ You cannot book a room for a past date.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })
    

    if booking_start_datetime <= now:
        return templates.TemplateResponse("book.html", {
            "request": request,
            "message": "❌ Cannot book for a past date/time.",
            "current_date": today.isoformat(),
            "room_map": room_map
        })

    
    # if booking_date == today and start < current_time:
    #     return templates.TemplateResponse("book.html", {
    #         "request": request,
    #         "message": "❌ Cannot book a past time slot for today.",
    #         "current_date": today.isoformat(),
    #         "room_map": room_map
    #     })

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
        user_id=int(user_id),
        room_number=available_room,
        date=booking_date,
        start_time=start,
        end_time=end
    )
    db.add(new_booking)
    db.commit()

    # refresh room_map after booking
    bookings = db.query(Booking).join(User).all()
    room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]

    return templates.TemplateResponse("book.html", {
        "request": request,
        "message": f"✅ Room {available_room} successfully booked!",
        "current_date": today.isoformat(),
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


# @router.get("/book", response_class=HTMLResponse)
# def book_form(request: Request, db: Session = Depends(get_db)):
#     bookings = db.query(Booking).join(User).all()
#     room_map = [(b.room_number, b.start_time, b.end_time, b.user.username) for b in bookings]
#     return templates.TemplateResponse("book.html", {
#         "request": request,
#         "room_map": room_map,
#         "msg": ""
#     })

