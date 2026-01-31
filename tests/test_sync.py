"""Tests for sync modules: Naver and CatchTable."""

import pytest

from src.sync.naver import NaverBookingSync
from src.sync.catchtable import CatchTableSync


class TestNaverBookingSync:
    """Tests for Naver Booking sync (unconfigured mode)."""

    def test_not_configured_without_credentials(self):
        sync = NaverBookingSync()
        assert sync._configured is False

    @pytest.mark.asyncio
    async def test_push_returns_none_when_not_configured(self):
        sync = NaverBookingSync()
        from unittest.mock import MagicMock
        mock_reservation = MagicMock()
        mock_reservation.reservation_code = "TEST0001"
        result = await sync.push_reservation(mock_reservation)
        assert result is None

    @pytest.mark.asyncio
    async def test_pull_returns_empty_when_not_configured(self):
        sync = NaverBookingSync()
        result = await sync.pull_reservations()
        assert result == []

    @pytest.mark.asyncio
    async def test_update_availability_returns_false_when_not_configured(self):
        sync = NaverBookingSync()
        result = await sync.update_availability("2025-02-03", [])
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_returns_false_when_not_configured(self):
        sync = NaverBookingSync()
        result = await sync.cancel_reservation("ext-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_close_without_client_is_safe(self):
        sync = NaverBookingSync()
        await sync.close()  # Should not raise


class TestCatchTableSync:
    """Tests for CatchTable sync (unconfigured mode)."""

    def test_not_configured_without_credentials(self):
        sync = CatchTableSync()
        assert sync._configured is False

    @pytest.mark.asyncio
    async def test_push_returns_none_when_not_configured(self):
        sync = CatchTableSync()
        from unittest.mock import MagicMock
        mock_reservation = MagicMock()
        mock_reservation.reservation_code = "TEST0002"
        result = await sync.push_reservation(mock_reservation)
        assert result is None

    @pytest.mark.asyncio
    async def test_pull_returns_empty_when_not_configured(self):
        sync = CatchTableSync()
        result = await sync.pull_reservations()
        assert result == []

    @pytest.mark.asyncio
    async def test_update_availability_returns_false_when_not_configured(self):
        sync = CatchTableSync()
        result = await sync.update_availability("2025-02-03", [])
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_returns_false_when_not_configured(self):
        sync = CatchTableSync()
        result = await sync.cancel_reservation("ext-456")
        assert result is False

    @pytest.mark.asyncio
    async def test_close_without_client_is_safe(self):
        sync = CatchTableSync()
        await sync.close()
