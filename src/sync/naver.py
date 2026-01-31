"""Naver Booking (네이버 예약) sync integration.

IMPORTANT: Naver Booking does NOT have a public API.
Access requires a formal partnership (제휴) with Naver Smart Place.

To apply for partnership:
1. Register restaurant on https://new.smartplace.naver.com/
2. Set up reservation service (일반형 6번 for restaurants)
3. Submit partnership proposal at https://www.navercorp.com/naver/proposalView
4. Or contact Naver Booking customer service: 1644-5690
5. After approval, receive private API documentation

This module provides the integration structure that will be completed
once API access is granted.

Known API behavior (from third-party integrations):
- Bidirectional sync with ~60 second delay
- Status flow: submitted -> confirmed -> completed/cancelled
- Inventory type must be per-person (명), not per-unit (건)
- Slot intervals: 30 minutes or 1 hour
- Naver Pay settlements handled exclusively through Naver Smart Place
"""

import structlog

from src.config import settings
from src.reservation.models import Reservation
from src.sync.base import PlatformSync

logger = structlog.get_logger()


class NaverBookingSync(PlatformSync):
    """Naver Booking sync implementation.

    Requires partnership agreement with Naver for API access.
    """

    def __init__(self) -> None:
        self.client_id = settings.naver_booking_client_id
        self.client_secret = settings.naver_booking_client_secret
        self.business_id = settings.naver_business_id
        self._configured = bool(self.client_id and self.client_secret)

    async def push_reservation(self, reservation: Reservation) -> str | None:
        if not self._configured:
            logger.warning("naver.not_configured")
            return None

        # TODO: Implement when Naver partner API access is granted
        # POST reservation data to Naver Booking API
        # Return Naver reservation ID
        logger.info("naver.push_reservation", code=reservation.reservation_code)
        return None

    async def pull_reservations(self) -> list[dict]:
        if not self._configured:
            return []

        # TODO: Implement when Naver partner API access is granted
        # GET new reservations from Naver
        # Transform to internal format
        logger.info("naver.pull_reservations")
        return []

    async def update_availability(self, date: str, slots: list[dict]) -> bool:
        if not self._configured:
            return False

        # TODO: Implement when Naver partner API access is granted
        # PUT availability/inventory data to Naver
        logger.info("naver.update_availability", date=date, slot_count=len(slots))
        return False

    async def cancel_reservation(self, external_id: str) -> bool:
        if not self._configured:
            return False

        # TODO: Implement when Naver partner API access is granted
        logger.info("naver.cancel_reservation", external_id=external_id)
        return False
