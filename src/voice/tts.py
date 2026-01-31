"""TTS (Text-to-Speech) provider integration for Korean speech synthesis.

Supports Naver CLOVA Voice Premium with:
- 60+ Korean voices (nara_call recommended for phone service)
- Emotion, speed, pitch control
- Sentence-level chunked synthesis for low-latency streaming
- WAV-to-PCM16 conversion for telephony (8kHz mono)
"""

import io
import struct
from collections.abc import AsyncGenerator

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()

# Available CLOVA Voice speakers (Korean)
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

# Sentence-ending markers for chunked synthesis
_SENTENCE_ENDERS = ("요.", "요?", "요!", "다.", "다?", "다!", ".", "!", "?")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences for chunked TTS.

    Splitting reduces time-to-first-byte by allowing the first
    sentence to play while later sentences are still synthesizing.
    """
    sentences: list[str] = []
    current = ""
    for char in text:
        current += char
        if any(current.rstrip().endswith(e) for e in _SENTENCE_ENDERS):
            stripped = current.strip()
            if stripped:
                sentences.append(stripped)
            current = ""
    remaining = current.strip()
    if remaining:
        sentences.append(remaining)
    return sentences if sentences else ([text.strip()] if text.strip() else [])


def wav_to_pcm16(wav_bytes: bytes, target_rate: int = 8000) -> bytes:
    """Extract raw PCM16 samples from a WAV file.

    Handles header parsing, stereo-to-mono conversion,
    and sample rate conversion via linear interpolation.
    """
    buf = io.BytesIO(wav_bytes)

    riff = buf.read(4)
    if riff != b"RIFF":
        raise ValueError("Not a valid WAV file (missing RIFF header)")
    buf.read(4)  # file size
    wave = buf.read(4)
    if wave != b"WAVE":
        raise ValueError("Not a valid WAV file (missing WAVE marker)")

    src_rate = 16000
    channels = 1
    pcm_data = b""

    while True:
        chunk_id = buf.read(4)
        if len(chunk_id) < 4:
            break
        chunk_size = struct.unpack("<I", buf.read(4))[0]

        if chunk_id == b"fmt ":
            fmt_data = buf.read(chunk_size)
            channels = struct.unpack("<H", fmt_data[2:4])[0]
            src_rate = struct.unpack("<I", fmt_data[4:8])[0]
        elif chunk_id == b"data":
            pcm_data = buf.read(chunk_size)
            break
        else:
            buf.read(chunk_size)

    if not pcm_data:
        raise ValueError("No audio data found in WAV file")

    # Stereo to mono
    if channels == 2:
        samples = struct.unpack(f"<{len(pcm_data) // 2}h", pcm_data)
        mono = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)]
        pcm_data = struct.pack(f"<{len(mono)}h", *mono)

    # Resample if needed
    if src_rate != target_rate:
        samples = struct.unpack(f"<{len(pcm_data) // 2}h", pcm_data)
        ratio = src_rate / target_rate
        new_len = int(len(samples) / ratio)
        resampled = []
        for i in range(new_len):
            src_idx = i * ratio
            idx = int(src_idx)
            frac = src_idx - idx
            if idx + 1 < len(samples):
                val = int(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
            else:
                val = samples[-1] if samples else 0
            resampled.append(max(-32768, min(32767, val)))
        pcm_data = struct.pack(f"<{len(resampled)}h", *resampled)

    return pcm_data


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
        self._http = httpx.AsyncClient(timeout=10.0)

    async def synthesize(
        self,
        text: str,
        *,
        speaker: str | None = None,
        speed: int = 0,
        pitch: int = 0,
        volume: int = 0,
        emotion: int = 0,
        output_format: str = "mp3",
    ) -> bytes:
        """Synthesize Korean text to speech audio.

        Args:
            text: Korean text to synthesize (max 5000 chars)
            speaker: Voice ID (default from config)
            speed: Speed (-5 to 5, 0=normal)
            pitch: Pitch (-5 to 5, 0=normal)
            volume: Volume (-5 to 5, 0=normal)
            emotion: Emotion intensity (0=neutral, 1=light, 2=strong)
            output_format: "mp3" or "wav"

        Returns:
            Audio bytes in the requested format
        """
        resp = await self._http.post(
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
                "format": output_format,
            },
        )
        resp.raise_for_status()
        return resp.content

    async def synthesize_streaming(
        self,
        text: str,
        *,
        speaker: str | None = None,
        speed: int = 0,
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text sentence-by-sentence for streaming playback.

        Yields:
            MP3 audio bytes for each sentence
        """
        sentences = split_sentences(text)
        for sentence in sentences:
            audio = await self.synthesize(sentence, speaker=speaker, speed=speed)
            yield audio

    async def synthesize_pcm(
        self,
        text: str,
        *,
        speaker: str | None = None,
        speed: int = 0,
        sample_rate: int = 8000,
    ) -> bytes:
        """Synthesize and return raw PCM16 audio at the target sample rate.

        For telephony, 8kHz mono PCM16 is the standard format.
        """
        wav_bytes = await self.synthesize(
            text, speaker=speaker, speed=speed, output_format="wav"
        )
        return wav_to_pcm16(wav_bytes, target_rate=sample_rate)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()


def create_tts() -> ClovaVoiceTTS:
    """Factory: create the TTS provider."""
    if not settings.clova_voice_client_id:
        raise ValueError("CLOVA_VOICE_CLIENT_ID not configured.")
    return ClovaVoiceTTS()
