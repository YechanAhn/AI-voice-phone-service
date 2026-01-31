"""Base interface for external platform sync."""

from abc import ABC, abstractmethod

from src.reservation.models import Reservation


class PlatformSync(ABC):
    """Abstract base class for syncing reservations with external platforms.

    Implementations handle bidirectional sync with platforms like
    Naver Booking, CatchTable, etc.
    """

    @abstractmethod
    async def push_reservation(self, reservation: Reservation) -> str | None:
        """Push a new reservation to the external platform.

        Returns:
            External platform reservation ID, or None if push failed.
        """
        ...

    @abstractmethod
    async def pull_reservations(self) -> list[dict]:
        """Pull new/updated reservations from the external platform.

        Returns:
            List of reservation data dicts from the platform.
        """
        ...

    @abstractmethod
    async def update_availability(self, date: str, slots: list[dict]) -> bool:
        """Update availability/inventory on the external platform.

        Args:
            date: Date to update (YYYY-MM-DD)
            slots: List of {time, remaining_capacity} dicts

        Returns:
            True if update succeeded.
        """
        ...

    @abstractmethod
    async def cancel_reservation(self, external_id: str) -> bool:
        """Cancel a reservation on the external platform.

        Args:
            external_id: The platform's reservation ID

        Returns:
            True if cancellation succeeded.
        """
        ...
