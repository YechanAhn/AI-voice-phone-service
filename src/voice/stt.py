"""STT (Speech-to-Text) provider integrations for Korean speech recognition."""

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()


class ReturnZeroSTT:
    """Return Zero (RTZR) STT client.

    Best Korean STT accuracy (CER ~5.9-6.8%).
    Supports streaming via gRPC/WebSocket with CALL mode for telephony.
    Docs: https://developers.rtzr.ai/docs/en/stt-streaming/
    """

    TOKEN_URL = "https://openapi.vito.ai/v1/authenticate"
    STREAMING_URL = "wss://openapi.vito.ai/v1/transcribe:streaming"

    def __init__(self) -> None:
        self.client_id = settings.rtzr_client_id
        self.client_secret = settings.rtzr_client_secret
        self._token: str | None = None

    async def get_token(self) -> str:
        """Authenticate and get access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
            return self._token

    def get_streaming_config(self) -> dict:
        """Return streaming configuration for CALL mode (telephony-optimized)."""
        return {
            "sample_rate": "8000",  # Telephony standard
            "encoding": "LINEAR16",
            "use_diarization": False,
            "use_itn": True,  # Inverse text normalization
            "use_disfluency_filter": True,
            "use_profanity_filter": False,
            "keywords": "예약,취소,변경,인원,시간,날짜,개인실",
        }


class ClovaSpeechSTT:
    """Naver CLOVA Speech STT client.

    Strong Korean alternative (CER ~7.5-8.1%).
    Recently added real-time streaming support.
    Docs: https://api.ncloud-docs.com/docs/en/ai-naver-clovaspeechrecognition
    """

    def __init__(self) -> None:
        self.secret_key = settings.clova_speech_secret_key
        self.invoke_url = settings.clova_speech_invoke_url

    def get_headers(self) -> dict:
        return {
            "X-CLOVASPEECH-API-KEY": self.secret_key,
            "Content-Type": "application/json",
        }

    def get_streaming_config(self) -> dict:
        return {
            "language": "ko",
            "completion": "sync",
            "format": "LINEAR16",
            "sampleRate": 8000,
            "boostings": [
                {"words": "예약,취소,변경,인원,시간"},
            ],
        }
