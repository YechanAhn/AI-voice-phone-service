"""Sync manager: orchestrates bidirectional sync across all platforms.

Runs as a background task, periodically:
1. Pulling new reservations from Naver/CatchTable
2. Pushing local phone reservations to external platforms
3. Updating availability across platforms after changes
"""

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_factory
from src.reservation.models import Reservation, ReservationSource, ReservationStatus
from src.sync.catchtable import CatchTableSync
from src.sync.naver import NaverBookingSync

logger = structlog.get_logger()


class SyncManager:
    """Coordinates reservation sync across Naver and CatchTable."""

    def __init__(self, restaurant_id: int) -> None:
        self.restaurant_id = restaurant_id
        self.naver = NaverBookingSync()
        self.catchtable = CatchTableSync()
        self._running = False

    async def start(self, interval_seconds: int = 60) -> None:
        """Start the periodic sync loop."""
        self._running = True
        logger.info("sync_manager.started", interval=interval_seconds)

        while self._running:
            try:
                await self.sync_once()
            except Exception:
                logger.exception("sync_manager.sync_error")
            await asyncio.sleep(interval_seconds)

    async def sync_once(self) -> None:
        """Run a single sync cycle: pull then push."""
        await self._pull_external_reservations()
        await self._push_local_reservations()

    async def _pull_external_reservations(self) -> None:
        """Pull new reservations from external platforms and save locally."""
        for platform_name, syncer in [("naver", self.naver), ("catchtable", self.catchtable)]:
            try:
                new_bookings = await syncer.pull_reservations()
                if not new_bookings:
                    continue

                async with async_session_factory() as db:
                    for booking in new_bookings:
                        await self._import_booking(db, booking, platform_name)
                    await db.commit()

            except Exception:
                logger.exception("sync_manager.pull_error", platform=platform_name)

    async def _import_booking(
        self, db: AsyncSession, booking: dict, platform: str
    ) -> None:
        """Import a single external booking into the local database.

        Skips if a reservation with the same external ID already exists.
        """
        external_id = booking.get("external_id", "")
        if not external_id:
            return

        # Check for duplicate
        if platform == "naver":
            existing = await db.execute(
                select(Reservation).where(
                    Reservation.naver_reservation_id == external_id
                )
            )
        else:
            existing = await db.execute(
                select(Reservation).where(
                    Reservation.catchtable_reservation_id == external_id
                )
            )

        if existing.scalar_one_or_none():
            return

        import secrets
        import string

        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

        source = ReservationSource.NAVER if platform == "naver" else ReservationSource.CATCHTABLE
        reservation = Reservation(
            restaurant_id=self.restaurant_id,
            reservation_code=code,
            customer_name=booking.get("customer_name", ""),
            customer_phone=booking.get("customer_phone", ""),
            date=booking.get("date", ""),
            time=booking.get("time", ""),
            party_size=booking.get("party_size", 0),
            special_requests=booking.get("special_requests", ""),
            status=ReservationStatus.CONFIRMED,
            source=source,
            naver_reservation_id=external_id if platform == "naver" else None,
            catchtable_reservation_id=external_id if platform == "catchtable" else None,
        )
        db.add(reservation)
        logger.info("sync_manager.imported", platform=platform, code=code)

    async def _push_local_reservations(self) -> None:
        """Push local phone reservations to external platforms."""
        async with async_session_factory() as db:
            # Find phone reservations not yet synced to external platforms
            query = select(Reservation).where(
                Reservation.restaurant_id == self.restaurant_id,
                Reservation.source == ReservationSource.PHONE,
                Reservation.status == ReservationStatus.CONFIRMED,
                Reservation.naver_reservation_id.is_(None),
            )
            result = await db.execute(query)
            unsync_reservations = result.scalars().all()

            for reservation in unsync_reservations:
                # Push to Naver
                naver_id = await self.naver.push_reservation(reservation)
                if naver_id:
                    reservation.naver_reservation_id = naver_id

                # Push to CatchTable
                ct_id = await self.catchtable.push_reservation(reservation)
                if ct_id:
                    reservation.catchtable_reservation_id = ct_id

            await db.commit()

    def stop(self) -> None:
        """Stop the sync loop."""
        self._running = False
        logger.info("sync_manager.stopped")

    async def close(self) -> None:
        """Clean up HTTP clients."""
        self.stop()
        await self.naver.close()
        await self.catchtable.close()
