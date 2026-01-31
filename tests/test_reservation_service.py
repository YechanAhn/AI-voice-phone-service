"""Tests for the reservation service business logic."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.reservation.models import (
    Reservation,
    ReservationSource,
    ReservationStatus,
    Restaurant,
    TimeSlot,
)
from src.reservation.schemas import (
    AvailabilityRequest,
    ReservationCancel,
    ReservationCreate,
    ReservationLookup,
    ReservationModify,
)
from src.reservation.service import ReservationService


@pytest.fixture
async def restaurant(db_session: AsyncSession) -> Restaurant:
    """Create a test restaurant with time slots."""
    restaurant = Restaurant(
        id=1,
        name="테스트 식당",
        phone="02-1234-5678",
        address="서울시 강남구",
        total_seats=40,
        private_rooms=2,
    )
    db_session.add(restaurant)

    # Add time slots for Monday (weekday=0)
    # 11:00-14:00, 17:00-22:00
    for start, end in [("11:00", "14:00"), ("17:00", "22:00")]:
        slot = TimeSlot(
            restaurant_id=1,
            day_of_week=0,
            start_time=start,
            end_time=end,
            max_capacity=20,
            slot_interval_minutes=30,
        )
        db_session.add(slot)

    await db_session.commit()
    return restaurant


@pytest.fixture
def service(db_session: AsyncSession) -> ReservationService:
    return ReservationService(db=db_session, restaurant_id=1)


class TestCheckAvailability:
    async def test_available_slot(self, service, restaurant):
        """Should return available=True for an open slot."""
        # 2025-02-03 is a Monday
        req = AvailabilityRequest(date="2025-02-03", time="18:00", party_size=4)
        result = await service.check_availability(req)
        assert result.available is True
        assert result.remaining_capacity == 20

    async def test_unavailable_no_slot(self, service, restaurant):
        """Should return available=False when no time slot exists."""
        # 15:00 is between lunch and dinner - no slot
        req = AvailabilityRequest(date="2025-02-03", time="15:00", party_size=4)
        result = await service.check_availability(req)
        assert result.available is False
        assert result.remaining_capacity == 0

    async def test_insufficient_capacity(self, service, restaurant, db_session):
        """Should return available=False when party exceeds remaining capacity."""
        # Pre-fill with 18 people
        reservation = Reservation(
            restaurant_id=1,
            reservation_code="TEST0001",
            customer_name="김테스트",
            customer_phone="010-0000-0000",
            date="2025-02-03",
            time="18:00",
            party_size=18,
            status=ReservationStatus.CONFIRMED,
            source=ReservationSource.PHONE,
        )
        db_session.add(reservation)
        await db_session.commit()

        req = AvailabilityRequest(date="2025-02-03", time="18:00", party_size=5)
        result = await service.check_availability(req)
        assert result.available is False
        assert result.remaining_capacity == 2


class TestCreateReservation:
    async def test_creates_reservation(self, service, restaurant):
        req = ReservationCreate(
            date="2025-02-03",
            time="18:00",
            party_size=4,
            customer_name="이예약",
            customer_phone="010-1234-5678",
            special_requests="창가 자리 부탁드립니다",
        )
        result = await service.create_reservation(req)
        assert result.reservation_code is not None
        assert len(result.reservation_code) == 8
        assert result.customer_name == "이예약"
        assert result.party_size == 4
        assert result.status == "confirmed"

    async def test_generates_unique_codes(self, service, restaurant):
        """Each reservation should get a unique code."""
        codes = set()
        for i in range(5):
            req = ReservationCreate(
                date="2025-02-03",
                time="18:00",
                party_size=2,
                customer_name=f"고객{i}",
                customer_phone=f"010-0000-{i:04d}",
            )
            result = await service.create_reservation(req)
            codes.add(result.reservation_code)
        assert len(codes) == 5


class TestCancelReservation:
    async def test_cancels_existing(self, service, restaurant, db_session):
        # Create a reservation first
        reservation = Reservation(
            restaurant_id=1,
            reservation_code="CANCEL01",
            customer_name="박취소",
            customer_phone="010-9876-5432",
            date="2025-02-03",
            time="18:00",
            party_size=3,
            status=ReservationStatus.CONFIRMED,
            source=ReservationSource.PHONE,
        )
        db_session.add(reservation)
        await db_session.commit()

        req = ReservationCancel(
            customer_name="박취소",
            customer_phone="010-9876-5432",
            reason="일정 변경",
        )
        result = await service.cancel_reservation(req)
        assert result["success"] is True
        assert "CANCEL01" in result["reservation_code"]

    async def test_cancel_not_found(self, service, restaurant):
        req = ReservationCancel(
            customer_name="없는사람",
            customer_phone="010-0000-0000",
        )
        result = await service.cancel_reservation(req)
        assert result["success"] is False

    async def test_cancel_already_cancelled(self, service, restaurant, db_session):
        reservation = Reservation(
            restaurant_id=1,
            reservation_code="CANCEL02",
            customer_name="최재취소",
            customer_phone="010-1111-2222",
            date="2025-02-03",
            time="19:00",
            party_size=2,
            status=ReservationStatus.CANCELLED,
            source=ReservationSource.PHONE,
        )
        db_session.add(reservation)
        await db_session.commit()

        req = ReservationCancel(
            reservation_code="CANCEL02",
            customer_name="최재취소",
            customer_phone="010-1111-2222",
        )
        result = await service.cancel_reservation(req)
        assert result["success"] is False


class TestModifyReservation:
    async def test_modify_date_and_time(self, service, restaurant, db_session):
        reservation = Reservation(
            restaurant_id=1,
            reservation_code="MODIFY01",
            customer_name="정변경",
            customer_phone="010-3333-4444",
            date="2025-02-03",
            time="18:00",
            party_size=4,
            status=ReservationStatus.CONFIRMED,
            source=ReservationSource.PHONE,
        )
        db_session.add(reservation)
        await db_session.commit()

        req = ReservationModify(
            customer_name="정변경",
            customer_phone="010-3333-4444",
            new_date="2025-02-04",
            new_time="19:00",
        )
        result = await service.modify_reservation(req)
        assert result["success"] is True
        assert result["date"] == "2025-02-04"
        assert result["time"] == "19:00"


class TestLookupReservation:
    async def test_lookup_by_code(self, service, restaurant, db_session):
        reservation = Reservation(
            restaurant_id=1,
            reservation_code="LOOK0001",
            customer_name="김조회",
            customer_phone="010-5555-6666",
            date="2025-02-03",
            time="18:30",
            party_size=2,
            status=ReservationStatus.CONFIRMED,
            source=ReservationSource.PHONE,
        )
        db_session.add(reservation)
        await db_session.commit()

        req = ReservationLookup(reservation_code="LOOK0001")
        result = await service.lookup_reservation(req)
        assert result["found"] is True
        assert result["customer_name"] == "김조회"

    async def test_lookup_by_name_phone(self, service, restaurant, db_session):
        reservation = Reservation(
            restaurant_id=1,
            reservation_code="LOOK0002",
            customer_name="이조회",
            customer_phone="010-7777-8888",
            date="2025-02-03",
            time="19:00",
            party_size=6,
            status=ReservationStatus.CONFIRMED,
            source=ReservationSource.PHONE,
        )
        db_session.add(reservation)
        await db_session.commit()

        req = ReservationLookup(customer_name="이조회", customer_phone="010-7777-8888")
        result = await service.lookup_reservation(req)
        assert result["found"] is True
        assert result["party_size"] == 6

    async def test_lookup_not_found(self, service, restaurant):
        req = ReservationLookup(reservation_code="NONEXIST")
        result = await service.lookup_reservation(req)
        assert result["found"] is False
