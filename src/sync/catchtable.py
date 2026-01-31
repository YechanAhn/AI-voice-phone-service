"""CatchTable (캐치테이블) sync integration.

CatchTable is Korea's #1 restaurant reservation platform.
(3.5M+ users, 10,000+ restaurants)

It already has Naver Booking sync built in, making it a practical
middleware for reaching Naver without direct partnership.

Partnership contact:
- B2B portal: https://biz.catchtable.co.kr/
- Email: service@catchtable.co.kr
- Phone: 1800-5895

CatchTable + Naver sync notes:
- CatchTable can sync Naver reservations into its own system
- Restaurant must use Naver Booking general type #6 (인원 단위)
- Time/party size settings must match between platforms
"""

from datetime import datetime

import httpx
import structlog

from src.config import settings
from src.reservation.models import Reservation
from src.sync.base import PlatformSync

logger = structlog.get_logger()

# Expected CatchTable B2B API base (provided after partnership)
_CATCHTABLE_API_BASE = "https://api.catchtable.co.kr/b2b/v1"


class CatchTableSync(PlatformSync):
    """CatchTable sync implementation.

    Requires B2B partnership with CatchTable for API access.
    API structure based on typical Korean reservation platform patterns.
    """

    def __init__(self) -> None:
        self.api_key = settings.catchtable_api_key
        self.restaurant_id = settings.catchtable_restaurant_id
        self._configured = bool(self.api_key and self.restaurant_id)
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=_CATCHTABLE_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
        return self._http

    async def push_reservation(self, reservation: Reservation) -> str | None:
        """Push a reservation to CatchTable."""
        if not self._configured:
            logger.warning("catchtable.not_configured")
            return None

        client = await self._get_client()

        payload = {
            "restaurantId": self.restaurant_id,
            "date": reservation.date,
            "time": reservation.time,
            "partySize": reservation.party_size,
            "guestName": reservation.customer_name,
            "guestPhone": reservation.customer_phone,
            "memo": reservation.special_requests or "",
            "externalCode": reservation.reservation_code,
            "status": "confirmed",
        }

        try:
            resp = await client.post("/reservations", json=payload)
            resp.raise_for_status()
            data = resp.json()
            ct_id = data.get("reservationId", "")
            logger.info(
                "catchtable.push_success",
                code=reservation.reservation_code,
                ct_id=ct_id,
            )
            return str(ct_id)
        except httpx.HTTPStatusError as e:
            logger.error("catchtable.push_failed", status=e.response.status_code)
            return None
        except httpx.RequestError as e:
            logger.error("catchtable.push_error", error=str(e))
            return None

    async def pull_reservations(self) -> list[dict]:
        """Pull new/updated reservations from CatchTable."""
        if not self._configured:
            return []

        client = await self._get_client()

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            resp = await client.get(
                f"/restaurants/{self.restaurant_id}/reservations",
                params={"startDate": today, "status": "pending"},
            )
            resp.raise_for_status()
            data = resp.json()

            reservations = []
            for r in data.get("reservations", []):
                reservations.append({
                    "external_id": str(r.get("reservationId", "")),
                    "date": r.get("date", ""),
                    "time": r.get("time", ""),
                    "party_size": r.get("partySize", 0),
                    "customer_name": r.get("guestName", ""),
                    "customer_phone": r.get("guestPhone", ""),
                    "special_requests": r.get("memo", ""),
                    "status": r.get("status", "pending"),
                    "source": "catchtable",
                })

            logger.info("catchtable.pull_success", count=len(reservations))
            return reservations

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("catchtable.pull_error", error=str(e))
            return []

    async def update_availability(self, date: str, slots: list[dict]) -> bool:
        """Update availability on CatchTable."""
        if not self._configured:
            return False

        client = await self._get_client()

        try:
            resp = await client.put(
                f"/restaurants/{self.restaurant_id}/availability",
                json={
                    "date": date,
                    "slots": [
                        {"time": s["time"], "capacity": s["remaining_capacity"]}
                        for s in slots
                    ],
                },
            )
            resp.raise_for_status()
            logger.info("catchtable.availability_updated", date=date, slots=len(slots))
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("catchtable.availability_failed", error=str(e))
            return False

    async def cancel_reservation(self, external_id: str) -> bool:
        """Cancel a reservation on CatchTable."""
        if not self._configured:
            return False

        client = await self._get_client()

        try:
            resp = await client.patch(
                f"/reservations/{external_id}",
                json={"status": "cancelled"},
            )
            resp.raise_for_status()
            logger.info("catchtable.cancel_success", external_id=external_id)
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("catchtable.cancel_failed", error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None
