"""IVR Voice Pipeline: simplified pipeline for the natural voice menu.

This is a lighter version of VoicePipeline that uses the VoiceIVR
for intent classification and FAQ responses instead of the full
reservation LLM. When the caller requests a reservation, it can
hand off to the full VoicePipeline seamlessly.

Architecture:
    Caller audio → VAD → STT → VoiceIVR → TTS → Caller
                                  │
                                  ├── FAQ match → instant response
                                  ├── Reservation → hand off to VoicePipeline
                                  └── Staff request → SIP transfer
"""

import asyncio

import structlog
from livekit import rtc

from src.voice.ivr import IVRConfig, VoiceIVR
from src.voice.pipeline import (
    BYTES_PER_FRAME,
    FRAME_DURATION_MS,
    NUM_CHANNELS,
    SAMPLE_RATE,
    SAMPLES_PER_FRAME,
    SILENCE_RMS_THRESHOLD,
    VoicePipeline,
    _rms,
)
from src.voice.stt import create_stt
from src.voice.tts import create_tts

logger = structlog.get_logger()


class IVRPipeline:
    """Simplified voice pipeline for natural IVR.

    Same audio infrastructure as VoicePipeline but uses
    keyword matching + lightweight LLM for faster responses.

    When the caller needs reservation service, hands off
    to the full VoicePipeline transparently.
    """

    def __init__(
        self,
        room: rtc.Room,
        ivr_config: IVRConfig | None = None,
        restaurant_id: int = 1,
    ) -> None:
        self.room = room
        self.restaurant_id = restaurant_id
        self.ivr = VoiceIVR(config=ivr_config)
        self.stt = create_stt()
        self.tts = create_tts()

        self._audio_source: rtc.AudioSource | None = None
        self._is_speaking = False
        self._cancel_playback = asyncio.Event()
        self._running = True
        self._handed_off = False
        self._reservation_pipeline: VoicePipeline | None = None

    async def start(self) -> None:
        """Initialize IVR pipeline and send greeting."""
        logger.info("ivr_pipeline.starting", restaurant=self.ivr.config.restaurant_name)

        await self.stt.connect()

        self._audio_source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        track = rtc.LocalAudioTrack.create_audio_track("agent-voice", self._audio_source)
        await self.room.local_participant.publish_track(track)

        # Send IVR greeting (faster than reservation greeting)
        await self._speak(self.ivr.greeting)

        # Start background STT receive loop
        asyncio.create_task(self._stt_receive_loop())

        logger.info("ivr_pipeline.started", menu=self.ivr.menu_summary)

    async def handle_audio_frame(self, frame: rtc.AudioFrame) -> None:
        """Process incoming audio frame from caller."""
        # If handed off to reservation pipeline, delegate
        if self._handed_off and self._reservation_pipeline:
            await self._reservation_pipeline.handle_audio_frame(frame)
            return

        audio_data = bytes(frame.data)
        energy = _rms(audio_data)

        if energy > SILENCE_RMS_THRESHOLD:
            if self._is_speaking:
                logger.info("ivr_pipeline.barge_in")
                self._cancel_playback.set()
            await self.stt.send_audio(audio_data)

    async def _stt_receive_loop(self) -> None:
        """Background: receive STT transcripts and process through IVR."""
        try:
            async for transcript in self.stt.receive_transcripts():
                if not self._running:
                    break
                if self._handed_off:
                    break

                text = transcript["text"]
                is_final = transcript["is_final"]

                if not is_final:
                    continue

                logger.info("ivr_pipeline.transcript", text=text)
                await self._process_ivr(text)

        except Exception:
            logger.exception("ivr_pipeline.stt_error")

    async def _process_ivr(self, text: str) -> None:
        """Process utterance through Voice IVR."""
        result = await self.ivr.process_utterance(text)

        action = result.get("action", "respond")

        # Speak the response
        if result.get("text"):
            await self._speak(result["text"])

        if action == "transfer_reservation":
            await self._handoff_to_reservation()

        elif action == "transfer_staff":
            logger.info("ivr_pipeline.transfer_staff")
            # In production, this would initiate a SIP REFER/transfer.
            # For now, we just end the IVR side.
            await self._speak("직원 연결 중이에요. 잠시만 기다려 주세요.")
            # TODO: Implement SIP transfer via LiveKit API
            self._running = False

        elif action == "end":
            logger.info("ivr_pipeline.conversation_done")
            await asyncio.sleep(1.0)
            self._running = False

        elif result.get("done"):
            self._running = False

    async def _handoff_to_reservation(self) -> None:
        """Seamlessly hand off to the full reservation AI pipeline.

        The caller doesn't notice any interruption — their audio
        stream continues, but now the full LLM handles the conversation.
        """
        logger.info("ivr_pipeline.handoff_to_reservation")
        self._handed_off = True

        # Close IVR's STT connection (reservation pipeline will create its own)
        await self.stt.close()

        # Create and start the full reservation pipeline
        # It reuses the same room and audio source
        self._reservation_pipeline = VoicePipeline(
            room=self.room,
            restaurant_name=self.ivr.config.restaurant_name,
            restaurant_id=self.restaurant_id,
        )
        # Share the audio source so we don't publish a second track
        self._reservation_pipeline._audio_source = self._audio_source
        self._reservation_pipeline._is_speaking = False

        # Connect the reservation pipeline's STT
        await self._reservation_pipeline.stt.connect()

        # Start the reservation STT receive loop
        asyncio.create_task(self._reservation_pipeline._stt_receive_loop())

        # Send a transition greeting
        await self._speak_via_reservation(
            "네, 예약 도와드릴게요. 날짜와 시간, 인원을 말씀해 주세요."
        )

        logger.info("ivr_pipeline.handoff_complete")

    async def _speak_via_reservation(self, text: str) -> None:
        """Speak using the reservation pipeline's speak method."""
        if self._reservation_pipeline:
            await self._reservation_pipeline._speak(text)

    async def _speak(self, text: str) -> None:
        """Synthesize and play back audio to the caller."""
        if not self._audio_source:
            return

        self._is_speaking = True
        self._cancel_playback.clear()

        try:
            logger.info("ivr_pipeline.speaking", text=text[:50])

            pcm_audio = await self.tts.synthesize_pcm(
                text, sample_rate=SAMPLE_RATE
            )

            offset = 0
            while offset < len(pcm_audio):
                if self._cancel_playback.is_set():
                    logger.info("ivr_pipeline.playback_cancelled")
                    break

                chunk = pcm_audio[offset: offset + BYTES_PER_FRAME]
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

                await asyncio.sleep(FRAME_DURATION_MS / 1000)

        except Exception:
            logger.exception("ivr_pipeline.speak_error")
        finally:
            self._is_speaking = False

    async def stop(self) -> None:
        """Shut down the pipeline."""
        self._running = False
        self._cancel_playback.set()

        if self._handed_off and self._reservation_pipeline:
            await self._reservation_pipeline.stop()
        else:
            await self.stt.close()

        await self.tts.close()
        logger.info("ivr_pipeline.stopped")

    @property
    def is_running(self) -> bool:
        """Whether the pipeline is still active."""
        if self._handed_off and self._reservation_pipeline:
            return self._reservation_pipeline._running
        return self._running
