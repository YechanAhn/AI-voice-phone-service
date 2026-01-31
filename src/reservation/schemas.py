"""Pydantic schemas for reservation data validation."""

from datetime import datetime

from pydantic import BaseModel, Field


class AvailabilityRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM")
    party_size: int = Field(..., ge=1, le=50)


class AvailabilityResponse(BaseModel):
    available: bool
    date: str
    time: str
    party_size: int
    remaining_capacity: int
    alternative_times: list[str] = []  # Suggested if unavailable


class ReservationCreate(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    party_size: int = Field(..., ge=1, le=50)
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_phone: str = Field(..., min_length=10, max_length=20)
    special_requests: str = ""


class ReservationResponse(BaseModel):
    reservation_code: str
    date: str
    time: str
    party_size: int
    customer_name: str
    status: str
    created_at: datetime


class ReservationCancel(BaseModel):
    reservation_code: str | None = None
    customer_name: str
    customer_phone: str
    reason: str = ""


class ReservationModify(BaseModel):
    reservation_code: str | None = None
    customer_name: str
    customer_phone: str
    new_date: str | None = None
    new_time: str | None = None
    new_party_size: int | None = None


class ReservationLookup(BaseModel):
    reservation_code: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
