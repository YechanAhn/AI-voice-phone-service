"""TTS (Text-to-Speech) provider integration for Korean speech synthesis."""

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()

# Available CLOVA Voice speakers (Korean)
# Full list: https://api.ncloud-docs.com/docs/en/ai-naver-clovavoice-ttspremium
KOREAN_VOICES = {
    "nara": "여성 (차분, 낭독체)",
    "nara_call": "여성 (상담원, 통화체)",
    "nminsang": "남성 (밝은)",
    "njinho": "남성 (차분)",
    "njihun": "남성 (부드러운)",
    "ndaeseong": "남성 (힘있는)",
    "nyejin": "여성 (밝은)",
    "nyoungmi": "여성 (부드러운)",
}


class ClovaVoiceTTS:
    """Naver CLOVA Voice Premium TTS client.

    60+ Korean voices with natural intonation.
    Supports emotion, speed, and pitch control.
    Recommended voice for phone service: 'nara_call' (상담원 톤)
    """

    API_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"

    def __init__(self) -> None:
        self.client_id = settings.clova_voice_client_id
        self.client_secret = settings.clova_voice_client_secret
        self.speaker = settings.clova_voice_speaker

    async def synthesize(
        self,
        text: str,
        *,
        speaker: str | None = None,
        speed: int = 0,
        pitch: int = 0,
        volume: int = 0,
        emotion: int = 0,
    ) -> bytes:
        """Synthesize Korean text to speech audio.

        Args:
            text: Korean text to synthesize (max 5000 chars)
            speaker: Voice ID (default from config)
            speed: Speed (-5 to 5, 0=normal)
            pitch: Pitch (-5 to 5, 0=normal)
            volume: Volume (-5 to 5, 0=normal)
            emotion: Emotion intensity (0=neutral, 1=light, 2=strong)

        Returns:
            MP3 audio bytes
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.API_URL,
                headers={
                    "X-NCP-APIGW-API-KEY-ID": self.client_id,
                    "X-NCP-APIGW-API-KEY": self.client_secret,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "speaker": speaker or self.speaker,
                    "text": text,
                    "speed": str(speed),
                    "pitch": str(pitch),
                    "volume": str(volume),
                    "emotion": str(emotion),
                    "format": "mp3",
                },
            )
            resp.raise_for_status()
            return resp.content
