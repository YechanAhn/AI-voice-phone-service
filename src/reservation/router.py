"""REST API endpoints for reservation management."""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db_session
from src.reservation.schemas import (
    AvailabilityRequest,
    AvailabilityResponse,
    ReservationCancel,
    ReservationCreate,
    ReservationLookup,
    ReservationModify,
    ReservationResponse,
)
from src.reservation.service import ReservationService

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async for session in get_db_session():
        yield session


async def get_service(
    db: AsyncSession = Depends(get_db),
    x_restaurant_id: int = Header(default=None),
) -> ReservationService:
    """Reservation service dependency.

    Restaurant ID comes from X-Restaurant-Id header or config default.
    """
    restaurant_id = x_restaurant_id or settings.restaurant_id
    return ReservationService(db=db, restaurant_id=restaurant_id)


@router.post("/check-availability", response_model=AvailabilityResponse)
async def check_availability(
    req: AvailabilityRequest,
    service: ReservationService = Depends(get_service),
) -> AvailabilityResponse:
    """Check if a time slot is available."""
    return await service.check_availability(req)


@router.post("/create", response_model=ReservationResponse)
async def create_reservation(
    req: ReservationCreate,
    service: ReservationService = Depends(get_service),
) -> ReservationResponse:
    """Create a new reservation."""
    return await service.create_reservation(req)


@router.post("/cancel")
async def cancel_reservation(
    req: ReservationCancel,
    service: ReservationService = Depends(get_service),
) -> dict:
    """Cancel an existing reservation."""
    return await service.cancel_reservation(req)


@router.post("/modify")
async def modify_reservation(
    req: ReservationModify,
    service: ReservationService = Depends(get_service),
) -> dict:
    """Modify an existing reservation."""
    return await service.modify_reservation(req)


@router.post("/lookup")
async def lookup_reservation(
    req: ReservationLookup,
    service: ReservationService = Depends(get_service),
) -> dict:
    """Look up a reservation."""
    return await service.lookup_reservation(req)
