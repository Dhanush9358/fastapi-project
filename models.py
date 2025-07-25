from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)
    security_key = Column(String, nullable=False)
    bookings = relationship("Booking", back_populates="user")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    room_number = Column(Integer)
    date = Column(String)  # <-- NEW FIELD
    start_time = Column(String)
    end_time = Column(String)
    name = Column(String)
    user = relationship("User", back_populates="bookings")
