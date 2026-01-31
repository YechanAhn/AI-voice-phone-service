"""Naver Booking (네이버 예약) sync integration.

IMPORTANT: Naver Booking does NOT have a public API.
Access requires a formal partnership (제휴) with Naver Smart Place.

To apply:
1. Register on https://new.smartplace.naver.com/
2. Set up reservation (일반형 6번, 인원(명) 단위)
3. Submit proposal at https://www.navercorp.com/naver/proposalView
4. Or call: 1644-5690
5. After approval, receive private API documentation

Known API behavior (from third-party integrations):
- Bidirectional sync with ~60 second delay
- Status flow: submitted -> confirmed -> completed/cancelled
- Completed/cancelled status is immutable
- Inventory type: per-person (명), not per-unit (건)
- Slot intervals: 30 minutes or 1 hour
"""

from datetime import datetime

import httpx
import structlog

from src.config import settings
from src.reservation.models import Reservation, ReservationStatus
from src.sync.base import PlatformSync

logger = structlog.get_logger()

# Expected Naver partner API base URL (provided after partnership approval)
_NAVER_API_BASE = "https://api.booking.naver.com/v1"


class NaverBookingSync(PlatformSync):
    """Naver Booking sync implementation.

    All API calls are structured to match known Naver Booking patterns.
    The actual endpoint URLs and auth flow will be confirmed after
    partnership approval. Current implementation uses the expected
    REST API structure based on third-party integration documentation.
    """

    def __init__(self) -> None:
        self.client_id = settings.naver_booking_client_id
        self.client_secret = settings.naver_booking_client_secret
        self.business_id = settings.naver_business_id
        self._configured = bool(self.client_id and self.client_secret and self.business_id)
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with auth headers."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=_NAVER_API_BASE,
                headers={
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
        return self._http

    async def push_reservation(self, reservation: Reservation) -> str | None:
        """Push a reservation to Naver Booking.

        Maps internal reservation to Naver's expected format:
        - bookingDate: YYYY-MM-DD
        - bookingTime: HH:MM
        - personCount: party_size (명 단위)
        - status: submitted -> confirmed flow
        """
        if not self._configured:
            logger.warning("naver.not_configured")
            return None

        client = await self._get_client()

        payload = {
            "businessId": self.business_id,
            "bookingDate": reservation.date,
            "bookingTime": reservation.time,
            "personCount": reservation.party_size,
            "bookerName": reservation.customer_name,
            "bookerPhone": reservation.customer_phone,
            "memo": reservation.special_requests or "",
            "status": "confirmed",
            "externalId": reservation.reservation_code,
        }

        try:
            resp = await client.post("/bookings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            naver_id = data.get("bookingId", "")
            logger.info(
                "naver.push_success",
                code=reservation.reservation_code,
                naver_id=naver_id,
            )
            return str(naver_id)
        except httpx.HTTPStatusError as e:
            logger.error("naver.push_failed", status=e.response.status_code, code=reservation.reservation_code)
            return None
        except httpx.RequestError as e:
            logger.error("naver.push_error", error=str(e))
            return None

    async def pull_reservations(self) -> list[dict]:
        """Pull new/updated reservations from Naver.

        Fetches bookings with status 'submitted' that need confirmation.
        Returns list of dicts with standardized reservation fields.
        """
        if not self._configured:
            return []

        client = await self._get_client()

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            resp = await client.get(
                "/bookings",
                params={
                    "businessId": self.business_id,
                    "startDate": today,
                    "status": "submitted",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            reservations = []
            for booking in data.get("bookings", []):
                reservations.append({
                    "external_id": str(booking.get("bookingId", "")),
                    "date": booking.get("bookingDate", ""),
                    "time": booking.get("bookingTime", ""),
                    "party_size": booking.get("personCount", 0),
                    "customer_name": booking.get("bookerName", ""),
                    "customer_phone": booking.get("bookerPhone", ""),
                    "special_requests": booking.get("memo", ""),
                    "status": booking.get("status", "submitted"),
                    "source": "naver",
                })

            logger.info("naver.pull_success", count=len(reservations))
            return reservations

        except httpx.HTTPStatusError as e:
            logger.error("naver.pull_failed", status=e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("naver.pull_error", error=str(e))
            return []

    async def update_availability(self, date: str, slots: list[dict]) -> bool:
        """Update availability on Naver.

        Naver uses per-person (명) inventory:
        slots = [{"time": "18:00", "remaining_capacity": 10}, ...]
        """
        if not self._configured:
            return False

        client = await self._get_client()

        inventory_items = [
            {
                "date": date,
                "time": slot["time"],
                "remainingCount": slot["remaining_capacity"],
            }
            for slot in slots
        ]

        try:
            resp = await client.put(
                f"/businesses/{self.business_id}/inventory",
                json={"items": inventory_items},
            )
            resp.raise_for_status()
            logger.info("naver.availability_updated", date=date, slots=len(slots))
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("naver.availability_update_failed", error=str(e))
            return False

    async def cancel_reservation(self, external_id: str) -> bool:
        """Cancel a reservation on Naver.

        Note: Only submitted/confirmed reservations can be cancelled.
        Completed/cancelled status is immutable in Naver's system.
        """
        if not self._configured:
            return False

        client = await self._get_client()

        try:
            resp = await client.patch(
                f"/bookings/{external_id}/status",
                json={"status": "cancelled"},
            )
            resp.raise_for_status()
            logger.info("naver.cancel_success", external_id=external_id)
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("naver.cancel_failed", external_id=external_id, error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None
