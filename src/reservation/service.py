"""Reservation business logic service."""

import secrets
import string
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.reservation.models import Reservation, ReservationSource, ReservationStatus, TimeSlot
from src.reservation.schemas import (
    AvailabilityRequest,
    AvailabilityResponse,
    ReservationCancel,
    ReservationCreate,
    ReservationLookup,
    ReservationModify,
    ReservationResponse,
)

logger = structlog.get_logger()


def _generate_reservation_code() -> str:
    """Generate a unique 8-character reservation code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))


class ReservationService:
    """Handles reservation CRUD operations.

    Called by the LLM via function calling when processing phone reservations.
    Also used by the REST API for direct management.
    """

    def __init__(self, db: AsyncSession, restaurant_id: int) -> None:
        self.db = db
        self.restaurant_id = restaurant_id

    async def check_availability(self, req: AvailabilityRequest) -> AvailabilityResponse:
        """Check if a time slot is available for the requested party size."""
        # Get total capacity for the time slot
        day_of_week = datetime.strptime(req.date, "%Y-%m-%d").weekday()
        slot_query = select(TimeSlot).where(
            TimeSlot.restaurant_id == self.restaurant_id,
            TimeSlot.day_of_week == day_of_week,
            TimeSlot.start_time <= req.time,
            TimeSlot.end_time > req.time,
        )
        result = await self.db.execute(slot_query)
        slot = result.scalar_one_or_none()

        if not slot:
            return AvailabilityResponse(
                available=False,
                date=req.date,
                time=req.time,
                party_size=req.party_size,
                remaining_capacity=0,
                alternative_times=[],
            )

        # Count existing reservations for this slot
        reservation_query = select(Reservation).where(
            Reservation.restaurant_id == self.restaurant_id,
            Reservation.date == req.date,
            Reservation.time == req.time,
            Reservation.status.in_([
                ReservationStatus.SUBMITTED,
                ReservationStatus.CONFIRMED,
            ]),
        )
        result = await self.db.execute(reservation_query)
        existing = result.scalars().all()
        booked_seats = sum(r.party_size for r in existing)
        remaining = slot.max_capacity - booked_seats

        available = remaining >= req.party_size

        # Find alternative times if not available
        alternative_times: list[str] = []
        if not available:
            alt_query = select(TimeSlot).where(
                TimeSlot.restaurant_id == self.restaurant_id,
                TimeSlot.day_of_week == day_of_week,
            )
            result = await self.db.execute(alt_query)
            all_slots = result.scalars().all()
            for s in all_slots:
                alternative_times.append(s.start_time)

        return AvailabilityResponse(
            available=available,
            date=req.date,
            time=req.time,
            party_size=req.party_size,
            remaining_capacity=max(0, remaining),
            alternative_times=alternative_times[:3],
        )

    async def create_reservation(self, req: ReservationCreate) -> ReservationResponse:
        """Create a new reservation."""
        code = _generate_reservation_code()

        reservation = Reservation(
            restaurant_id=self.restaurant_id,
            reservation_code=code,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            date=req.date,
            time=req.time,
            party_size=req.party_size,
            special_requests=req.special_requests,
            status=ReservationStatus.CONFIRMED,
            source=ReservationSource.PHONE,
        )

        self.db.add(reservation)
        await self.db.commit()
        await self.db.refresh(reservation)

        logger.info(
            "reservation.created",
            code=code,
            customer=req.customer_name,
            date=req.date,
            time=req.time,
            party_size=req.party_size,
        )

        return ReservationResponse(
            reservation_code=reservation.reservation_code,
            date=reservation.date,
            time=reservation.time,
            party_size=reservation.party_size,
            customer_name=reservation.customer_name,
            status=reservation.status.value,
            created_at=reservation.created_at,
        )

    async def cancel_reservation(self, req: ReservationCancel) -> dict:
        """Cancel an existing reservation."""
        reservation = await self._find_reservation(
            code=req.reservation_code,
            name=req.customer_name,
            phone=req.customer_phone,
        )

        if not reservation:
            return {"success": False, "message": "예약을 찾을 수 없습니다"}

        if reservation.status in (ReservationStatus.COMPLETED, ReservationStatus.CANCELLED):
            return {"success": False, "message": "이미 완료되었거나 취소된 예약입니다"}

        reservation.status = ReservationStatus.CANCELLED
        reservation.cancellation_reason = req.reason
        await self.db.commit()

        logger.info(
            "reservation.cancelled",
            code=reservation.reservation_code,
            reason=req.reason,
        )

        return {
            "success": True,
            "message": f"예약번호 {reservation.reservation_code} 취소가 완료되었습니다",
            "reservation_code": reservation.reservation_code,
        }

    async def modify_reservation(self, req: ReservationModify) -> dict:
        """Modify an existing reservation."""
        reservation = await self._find_reservation(
            code=req.reservation_code,
            name=req.customer_name,
            phone=req.customer_phone,
        )

        if not reservation:
            return {"success": False, "message": "예약을 찾을 수 없습니다"}

        if req.new_date:
            reservation.date = req.new_date
        if req.new_time:
            reservation.time = req.new_time
        if req.new_party_size:
            reservation.party_size = req.new_party_size

        await self.db.commit()

        logger.info(
            "reservation.modified",
            code=reservation.reservation_code,
            new_date=req.new_date,
            new_time=req.new_time,
            new_party_size=req.new_party_size,
        )

        return {
            "success": True,
            "message": "예약이 변경되었습니다",
            "reservation_code": reservation.reservation_code,
            "date": reservation.date,
            "time": reservation.time,
            "party_size": reservation.party_size,
        }

    async def lookup_reservation(self, req: ReservationLookup) -> dict:
        """Look up a reservation by code, name, or phone."""
        reservation = await self._find_reservation(
            code=req.reservation_code,
            name=req.customer_name,
            phone=req.customer_phone,
        )

        if not reservation:
            return {"found": False, "message": "예약을 찾을 수 없습니다"}

        return {
            "found": True,
            "reservation_code": reservation.reservation_code,
            "date": reservation.date,
            "time": reservation.time,
            "party_size": reservation.party_size,
            "customer_name": reservation.customer_name,
            "status": reservation.status.value,
            "special_requests": reservation.special_requests,
        }

    async def _find_reservation(
        self,
        code: str | None = None,
        name: str | None = None,
        phone: str | None = None,
    ) -> Reservation | None:
        """Find a reservation by code or name+phone combination."""
        if code:
            query = select(Reservation).where(
                Reservation.restaurant_id == self.restaurant_id,
                Reservation.reservation_code == code,
            )
        elif name and phone:
            query = (
                select(Reservation)
                .where(
                    Reservation.restaurant_id == self.restaurant_id,
                    Reservation.customer_name == name,
                    Reservation.customer_phone == phone,
                    Reservation.status.in_([
                        ReservationStatus.SUBMITTED,
                        ReservationStatus.CONFIRMED,
                    ]),
                )
                .order_by(Reservation.created_at.desc())
            )
        else:
            return None

        result = await self.db.execute(query)
        return result.scalar_one_or_none()
