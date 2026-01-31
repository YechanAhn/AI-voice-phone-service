"""STT (Speech-to-Text) provider integrations for Korean speech recognition.

Supports two providers:
- Return Zero (RTZR): Best Korean accuracy (CER ~5.9-6.8%)
- Naver CLOVA Speech: Strong alternative (CER ~7.5-8.1%)

Both support real-time streaming via WebSocket for phone conversations.
"""

import json
import time
from collections.abc import AsyncGenerator
from typing import Protocol

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()


class STTProvider(Protocol):
    """Protocol that all STT providers must implement."""

    async def connect(self) -> None: ...
    async def send_audio(self, audio_chunk: bytes) -> None: ...
    async def receive_transcripts(self) -> AsyncGenerator[dict, None]: ...
    async def end_utterance(self) -> None: ...
    async def close(self) -> None: ...


class ReturnZeroSTT:
    """Return Zero (RTZR) STT client with streaming support.

    Best Korean STT accuracy (CER ~5.9-6.8%).
    Uses WebSocket for real-time streaming.
    Docs: https://developers.rtzr.ai/
    """

    TOKEN_URL = "https://openapi.vito.ai/v1/authenticate"
    STREAMING_URL = "wss://openapi.vito.ai/v1/transcribe:streaming"

    def __init__(self) -> None:
        self.client_id = settings.rtzr_client_id
        self.client_secret = settings.rtzr_client_secret
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._ws = None  # websockets.ClientConnection

    async def _ensure_token(self) -> str:
        """Authenticate and get/refresh access token."""
        if self._token and time.time() < self._token_expires_at:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 21600) - 300
            return self._token

    def _streaming_config(self) -> dict:
        """Streaming configuration optimized for phone calls."""
        return {
            "sample_rate": "8000",
            "encoding": "LINEAR16",
            "use_diarization": "false",
            "use_itn": "true",
            "use_disfluency_filter": "true",
            "use_profanity_filter": "false",
            "keywords": "예약,취소,변경,인원,시간,날짜,개인실,이름,전화번호",
        }

    async def connect(self) -> None:
        """Open a streaming WebSocket connection."""
        from websockets.asyncio.client import connect as ws_connect

        token = await self._ensure_token()
        config = self._streaming_config()
        query = "&".join(f"{k}={v}" for k, v in config.items())
        url = f"{self.STREAMING_URL}?{query}"
        self._ws = await ws_connect(
            url,
            additional_headers={"Authorization": f"Bearer {token}"},
        )
        logger.info("rtzr_stt.connected")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send a PCM16 audio chunk to the streaming STT."""
        if self._ws is None:
            raise RuntimeError("STT not connected. Call connect() first.")
        await self._ws.send(audio_chunk)

    async def receive_transcripts(self) -> AsyncGenerator[dict, None]:
        """Yield transcript results as they arrive.

        Yields dicts with:
            - "text": transcribed text
            - "is_final": whether this is a final result
            - "confidence": confidence score 0-1
        """
        if self._ws is None:
            raise RuntimeError("STT not connected. Call connect() first.")

        import websockets

        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    continue
                data = json.loads(message)
                if "alternatives" in data:
                    for alt in data["alternatives"]:
                        text = alt.get("text", "").strip()
                        if text:
                            yield {
                                "text": text,
                                "is_final": data.get("is_final", False),
                                "confidence": alt.get("confidence", 0.0),
                            }
        except websockets.exceptions.ConnectionClosed:
            logger.info("rtzr_stt.connection_closed")

    async def end_utterance(self) -> None:
        """Signal end of speech."""
        if self._ws:
            await self._ws.send(b"")

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("rtzr_stt.disconnected")


class ClovaSpeechSTT:
    """Naver CLOVA Speech STT client with streaming support.

    Strong Korean alternative (CER ~7.5-8.1%).
    Uses WebSocket for real-time streaming.
    Docs: https://api.ncloud-docs.com/docs/en/ai-naver-clovaspeechrecognition
    """

    STREAMING_URL = "wss://clovaspeech-gw.ncloud.com/recog/v1/stt"

    def __init__(self) -> None:
        self.secret_key = settings.clova_speech_secret_key
        self.invoke_url = settings.clova_speech_invoke_url
        self._ws = None

    def _streaming_config(self) -> dict:
        return {
            "language": "ko",
            "completion": "sync",
            "format": "LINEAR16",
            "sampleRate": 8000,
            "boostings": [
                {"words": "예약,취소,변경,인원,시간"},
            ],
        }

    async def connect(self) -> None:
        """Open a streaming WebSocket connection to CLOVA Speech."""
        from websockets.asyncio.client import connect as ws_connect

        url = self.invoke_url or self.STREAMING_URL
        self._ws = await ws_connect(
            url,
            additional_headers={"X-CLOVASPEECH-API-KEY": self.secret_key},
        )
        config = self._streaming_config()
        await self._ws.send(json.dumps(config))
        logger.info("clova_stt.connected")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send PCM16 audio chunk to CLOVA streaming STT."""
        if self._ws is None:
            raise RuntimeError("STT not connected. Call connect() first.")
        await self._ws.send(audio_chunk)

    async def receive_transcripts(self) -> AsyncGenerator[dict, None]:
        """Yield transcript results from CLOVA Speech."""
        if self._ws is None:
            raise RuntimeError("STT not connected. Call connect() first.")

        import websockets

        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    continue
                data = json.loads(message)
                msg_type = data.get("type", "")
                if msg_type in ("recognized", "partial"):
                    text = data.get("text", "").strip()
                    if text:
                        yield {
                            "text": text,
                            "is_final": msg_type == "recognized",
                            "confidence": data.get("confidence", 0.0),
                        }
        except websockets.exceptions.ConnectionClosed:
            logger.info("clova_stt.connection_closed")

    async def end_utterance(self) -> None:
        """Signal end of speech."""
        if self._ws:
            await self._ws.send(b"")

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("clova_stt.disconnected")


def create_stt() -> ReturnZeroSTT | ClovaSpeechSTT:
    """Factory: return the configured STT provider.

    Prefers RTZR if configured, falls back to CLOVA Speech.
    """
    if settings.rtzr_client_id and settings.rtzr_client_secret:
        return ReturnZeroSTT()
    if settings.clova_speech_secret_key:
        return ClovaSpeechSTT()
    raise ValueError(
        "No STT provider configured. Set RTZR_CLIENT_ID/SECRET or CLOVA_SPEECH_SECRET_KEY."
    )
