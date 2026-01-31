"""Voice pipeline: VAD -> STT -> LLM -> TTS for phone conversations.

This is the core real-time audio processing loop. It connects
to a LiveKit room, listens to the caller's audio, transcribes it,
generates a response via LLM, synthesizes speech, and plays it back.
"""

import asyncio
import json
from typing import Any

import structlog
from livekit import rtc

from src.config import settings
from src.database import async_session_factory
from src.reservation.schemas import (
    AvailabilityRequest,
    ReservationCancel,
    ReservationCreate,
    ReservationLookup,
    ReservationModify,
)
from src.reservation.service import ReservationService
from src.voice.llm import ReservationLLM
from src.voice.stt import ReturnZeroSTT, ClovaSpeechSTT, create_stt
from src.voice.tts import ClovaVoiceTTS, create_tts

logger = structlog.get_logger()

# Telephony audio format: 8kHz, 16-bit, mono
SAMPLE_RATE = 8000
NUM_CHANNELS = 1
FRAME_DURATION_MS = 20
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_DURATION_MS // 1000  # 160
BYTES_PER_FRAME = SAMPLES_PER_FRAME * 2  # 320 bytes (16-bit)

# Silence detection: how many consecutive silent frames trigger end-of-speech
SILENCE_FRAMES_THRESHOLD = 30  # 30 * 20ms = 600ms of silence
# RMS threshold below which a frame is considered silence
SILENCE_RMS_THRESHOLD = 200


def _rms(audio: bytes) -> float:
    """Calculate root-mean-square energy of PCM16 audio."""
    import struct

    if len(audio) < 2:
        return 0.0
    n_samples = len(audio) // 2
    samples = struct.unpack(f"<{n_samples}h", audio[: n_samples * 2])
    return (sum(s * s for s in samples) / n_samples) ** 0.5


class FunctionCallHandler:
    """Executes LLM function calls against the reservation service.

    When the LLM decides to call a function (e.g. create_reservation),
    this handler maps the call to the appropriate service method,
    executes it, and returns the result as a JSON string.
    """

    def __init__(self, restaurant_id: int) -> None:
        self.restaurant_id = restaurant_id

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a function call and return the JSON result."""
        async with async_session_factory() as db:
            service = ReservationService(db=db, restaurant_id=self.restaurant_id)

            if name == "check_availability":
                result = await service.check_availability(
                    AvailabilityRequest(**arguments)
                )
                return json.dumps(result.model_dump(), ensure_ascii=False, default=str)

            elif name == "create_reservation":
                result = await service.create_reservation(
                    ReservationCreate(**arguments)
                )
                return json.dumps(result.model_dump(), ensure_ascii=False, default=str)

            elif name == "cancel_reservation":
                result = await service.cancel_reservation(
                    ReservationCancel(**arguments)
                )
                return json.dumps(result, ensure_ascii=False, default=str)

            elif name == "modify_reservation":
                result = await service.modify_reservation(
                    ReservationModify(**arguments)
                )
                return json.dumps(result, ensure_ascii=False, default=str)

            elif name == "lookup_reservation":
                result = await service.lookup_reservation(
                    ReservationLookup(**arguments)
                )
                return json.dumps(result, ensure_ascii=False, default=str)

            else:
                return json.dumps({"error": f"Unknown function: {name}"})


class VoicePipeline:
    """Real-time voice conversation pipeline.

    Manages the full audio loop:
    1. Receive caller audio from LiveKit
    2. VAD (Voice Activity Detection) via RMS energy
    3. Stream audio to STT for transcription
    4. Send transcript to LLM for response
    5. Execute any function calls from LLM
    6. Synthesize response via TTS
    7. Play audio back to caller via LiveKit

    Handles barge-in (caller interrupts while AI is speaking)
    by cancelling TTS playback and processing the new utterance.
    """

    def __init__(
        self,
        room: rtc.Room,
        restaurant_name: str,
        restaurant_id: int = 1,
    ) -> None:
        self.room = room
        self.restaurant_name = restaurant_name
        self.stt = create_stt()
        self.tts = create_tts()
        self.llm = ReservationLLM(restaurant_name=restaurant_name)
        self.fn_handler = FunctionCallHandler(restaurant_id=restaurant_id)

        self._audio_source: rtc.AudioSource | None = None
        self._is_speaking = False
        self._cancel_playback = asyncio.Event()
        self._running = True

    async def start(self) -> None:
        """Initialize pipeline components and start processing."""
        logger.info("pipeline.starting", restaurant=self.restaurant_name)

        # Connect STT
        await self.stt.connect()

        # Create audio source for publishing AI speech to the room
        self._audio_source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        track = rtc.LocalAudioTrack.create_audio_track("agent-voice", self._audio_source)
        await self.room.local_participant.publish_track(track)

        # Send initial greeting
        greeting = f"안녕하세요, {self.restaurant_name}입니다. 예약 도와드릴까요?"
        await self._speak(greeting)

        # Start background tasks
        asyncio.create_task(self._stt_receive_loop())

        logger.info("pipeline.started")

    async def handle_audio_frame(self, frame: rtc.AudioFrame) -> None:
        """Process an incoming audio frame from the caller.

        Called by the agent for each audio frame received from
        the SIP participant's audio track.
        """
        audio_data = bytes(frame.data)

        # Simple VAD: check if frame has speech energy
        energy = _rms(audio_data)

        if energy > SILENCE_RMS_THRESHOLD:
            # Speech detected - if AI is currently speaking, barge-in
            if self._is_speaking:
                logger.info("pipeline.barge_in")
                self._cancel_playback.set()

            # Send audio to STT
            await self.stt.send_audio(audio_data)

    async def _stt_receive_loop(self) -> None:
        """Background task: receive transcripts from STT and process them."""
        try:
            async for transcript in self.stt.receive_transcripts():
                if not self._running:
                    break

                text = transcript["text"]
                is_final = transcript["is_final"]

                if not is_final:
                    logger.debug("pipeline.partial_transcript", text=text)
                    continue

                logger.info("pipeline.final_transcript", text=text)
                await self._process_utterance(text)

        except Exception:
            logger.exception("pipeline.stt_receive_error")

    async def _process_utterance(self, text: str) -> None:
        """Process a complete user utterance through LLM -> function -> TTS."""
        # Get LLM response
        response = await self.llm.process_message(text)

        # Handle function calls (may require multiple rounds)
        while response.get("function_call"):
            fc = response["function_call"]
            logger.info("pipeline.function_call", name=fc["name"], args=fc["arguments"])

            result = await self.fn_handler.execute(fc["name"], fc["arguments"])
            response = await self.llm.provide_function_result(fc["id"], result)

        # Speak the response
        if response.get("text"):
            await self._speak(response["text"])

        # End call if conversation is done
        if response.get("done"):
            logger.info("pipeline.conversation_done")
            await asyncio.sleep(1.5)  # Let final audio play out
            self._running = False

    async def _speak(self, text: str) -> None:
        """Synthesize text and play it back to the caller."""
        if not self._audio_source:
            return

        self._is_speaking = True
        self._cancel_playback.clear()

        try:
            logger.info("pipeline.speaking", text=text[:50])

            # Synthesize to PCM16 at 8kHz for telephony
            pcm_audio = await self.tts.synthesize_pcm(
                text, sample_rate=SAMPLE_RATE
            )

            # Stream PCM in 20ms frames
            offset = 0
            while offset < len(pcm_audio):
                if self._cancel_playback.is_set():
                    logger.info("pipeline.playback_cancelled")
                    break

                chunk = pcm_audio[offset : offset + BYTES_PER_FRAME]
                if len(chunk) < BYTES_PER_FRAME:
                    chunk = chunk + b"\x00" * (BYTES_PER_FRAME - len(chunk))

                frame = rtc.AudioFrame(
                    data=chunk,
                    sample_rate=SAMPLE_RATE,
                    num_channels=NUM_CHANNELS,
                    samples_per_channel=SAMPLES_PER_FRAME,
                )
                await self._audio_source.capture_frame(frame)
                offset += BYTES_PER_FRAME

                # Pace at real-time
                await asyncio.sleep(FRAME_DURATION_MS / 1000)

        except Exception:
            logger.exception("pipeline.speak_error")
        finally:
            self._is_speaking = False

    async def stop(self) -> None:
        """Shut down the pipeline and release resources."""
        self._running = False
        self._cancel_playback.set()
        await self.stt.close()
        await self.tts.close()
        logger.info("pipeline.stopped")
