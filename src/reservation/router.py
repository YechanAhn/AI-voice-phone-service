"""REST API endpoints for reservation management."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

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


# TODO: Implement proper dependency injection for db session
async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Database session dependency (to be connected with actual engine)."""
    raise NotImplementedError("Database session not configured yet")


async def get_service(db: AsyncSession = Depends(get_db)) -> ReservationService:
    # TODO: Get restaurant_id from request context
    return ReservationService(db=db, restaurant_id=1)


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
