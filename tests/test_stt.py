"""Tests for STT module: factory, config, and protocol compliance."""

import os
from unittest.mock import patch

import pytest

from src.voice.stt import ReturnZeroSTT, ClovaSpeechSTT, create_stt


class TestReturnZeroSTT:
    """Unit tests for RTZR STT provider."""

    def test_streaming_config_format(self):
        """Config values should be strings for URL query params."""
        stt = ReturnZeroSTT()
        config = stt._streaming_config()
        assert config["sample_rate"] == "8000"
        assert config["encoding"] == "LINEAR16"
        assert config["use_itn"] == "true"
        assert "예약" in config["keywords"]

    def test_initial_state(self):
        stt = ReturnZeroSTT()
        assert stt._token is None
        assert stt._ws is None
        assert stt._token_expires_at == 0

    def test_send_audio_without_connect_raises(self):
        stt = ReturnZeroSTT()
        with pytest.raises(RuntimeError, match="not connected"):
            # Need to run async but since _ws is None it raises immediately
            import asyncio
            asyncio.get_event_loop().run_until_complete(stt.send_audio(b"data"))

    def test_close_without_connect_is_safe(self):
        """Closing without connecting should not raise."""
        import asyncio
        stt = ReturnZeroSTT()
        asyncio.get_event_loop().run_until_complete(stt.close())
        assert stt._ws is None


class TestClovaSpeechSTT:
    """Unit tests for CLOVA Speech STT provider."""

    def test_streaming_config(self):
        stt = ClovaSpeechSTT()
        config = stt._streaming_config()
        assert config["language"] == "ko"
        assert config["sampleRate"] == 8000
        assert config["format"] == "LINEAR16"

    def test_initial_state(self):
        stt = ClovaSpeechSTT()
        assert stt._ws is None

    def test_send_audio_without_connect_raises(self):
        stt = ClovaSpeechSTT()
        with pytest.raises(RuntimeError, match="not connected"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(stt.send_audio(b"data"))


class TestCreateSTT:
    """Test the STT factory function."""

    def test_prefers_rtzr_when_configured(self):
        """Should return ReturnZeroSTT when RTZR credentials are set."""
        with patch.dict(os.environ, {
            "RTZR_CLIENT_ID": "test_id",
            "RTZR_CLIENT_SECRET": "test_secret",
        }):
            from src.config import Settings
            with patch("src.voice.stt.settings", Settings()):
                stt = create_stt()
                assert isinstance(stt, ReturnZeroSTT)

    def test_falls_back_to_clova(self):
        """Should return ClovaSpeechSTT when only CLOVA is configured."""
        with patch.dict(os.environ, {
            "RTZR_CLIENT_ID": "",
            "RTZR_CLIENT_SECRET": "",
            "CLOVA_SPEECH_SECRET_KEY": "test_key",
        }):
            from src.config import Settings
            with patch("src.voice.stt.settings", Settings()):
                stt = create_stt()
                assert isinstance(stt, ClovaSpeechSTT)

    def test_raises_when_nothing_configured(self):
        """Should raise when no STT provider is configured."""
        with patch.dict(os.environ, {
            "RTZR_CLIENT_ID": "",
            "RTZR_CLIENT_SECRET": "",
            "CLOVA_SPEECH_SECRET_KEY": "",
        }):
            from src.config import Settings
            with patch("src.voice.stt.settings", Settings()):
                with pytest.raises(ValueError, match="No STT provider"):
                    create_stt()
