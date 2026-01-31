"""CatchTable (캐치테이블) sync integration.

CatchTable is Korea's #1 restaurant reservation platform (3.5M+ users, 10,000+ restaurants).
It already has a working integration with Naver Booking, making it a good middleware option.

Partnership contact:
- B2B portal: https://biz.catchtable.co.kr/
- Email: service@catchtable.co.kr
- Phone: 1800-5895

CatchTable + Naver integration notes:
- CatchTable can sync Naver reservations into its own system
- Restaurant must use Naver Booking general type #6 with per-person inventory
- Initial sync is one-directional (Naver -> CatchTable)
- Time/party size settings must match between platforms
"""

import structlog

from src.config import settings
from src.reservation.models import Reservation
from src.sync.base import PlatformSync

logger = structlog.get_logger()


class CatchTableSync(PlatformSync):
    """CatchTable sync implementation.

    Requires B2B partnership with CatchTable for API access.
    """

    def __init__(self) -> None:
        self.api_key = settings.catchtable_api_key
        self.restaurant_id = settings.catchtable_restaurant_id
        self._configured = bool(self.api_key and self.restaurant_id)

    async def push_reservation(self, reservation: Reservation) -> str | None:
        if not self._configured:
            logger.warning("catchtable.not_configured")
            return None

        # TODO: Implement when CatchTable B2B API access is granted
        logger.info("catchtable.push_reservation", code=reservation.reservation_code)
        return None

    async def pull_reservations(self) -> list[dict]:
        if not self._configured:
            return []

        # TODO: Implement when CatchTable B2B API access is granted
        logger.info("catchtable.pull_reservations")
        return []

    async def update_availability(self, date: str, slots: list[dict]) -> bool:
        if not self._configured:
            return False

        # TODO: Implement when CatchTable B2B API access is granted
        logger.info("catchtable.update_availability", date=date, slot_count=len(slots))
        return False

    async def cancel_reservation(self, external_id: str) -> bool:
        if not self._configured:
            return False

        # TODO: Implement when CatchTable B2B API access is granted
        logger.info("catchtable.cancel_reservation", external_id=external_id)
        return False
