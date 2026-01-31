"""Database models for the reservation system."""

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ReservationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReservationSource(str, enum.Enum):
    PHONE = "phone"          # AI phone booking
    NAVER = "naver"          # Naver Booking
    CATCHTABLE = "catchtable"  # CatchTable
    WALK_IN = "walk_in"      # Walk-in
    MANUAL = "manual"        # Staff manual entry


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    naver_business_id: Mapped[str | None] = mapped_column(String(100))
    catchtable_id: Mapped[str | None] = mapped_column(String(100))
    total_seats: Mapped[int] = mapped_column(Integer, default=0)
    private_rooms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    time_slots: Mapped[list["TimeSlot"]] = relationship(back_populates="restaurant")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="restaurant")


class TimeSlot(Base):
    """Available time slots for a restaurant.

    Naver uses 30-minute or 1-hour intervals.
    Inventory type must be per-person (명) for Naver compatibility.
    """

    __tablename__ = "time_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon, 6=Sun
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)    # HH:MM
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="time_slots")

    __table_args__ = (
        UniqueConstraint("restaurant_id", "day_of_week", "start_time"),
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    reservation_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Customer info
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)

    # Reservation details
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    time: Mapped[str] = mapped_column(String(5), nullable=False)   # HH:MM
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    special_requests: Mapped[str] = mapped_column(Text, default="")

    # Status tracking
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.CONFIRMED
    )
    source: Mapped[ReservationSource] = mapped_column(
        Enum(ReservationSource), default=ReservationSource.PHONE
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    # External platform IDs (for sync)
    naver_reservation_id: Mapped[str | None] = mapped_column(String(100))
    catchtable_reservation_id: Mapped[str | None] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    restaurant: Mapped["Restaurant"] = relationship(back_populates="reservations")
