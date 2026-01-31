"""Pipecat voice pipeline configuration for the reservation agent."""

import structlog

logger = structlog.get_logger()

# Pipeline architecture:
#
# AudioInput (from LiveKit room)
#     │
#     ▼
# Silero VAD (voice activity detection)
#     │
#     ▼
# STT (RTZR or CLOVA Speech)
#     │
#     ▼
# ReservationLLM (GPT-4o with function calling)
#     │
#     ▼
# TTS (CLOVA Voice)
#     │
#     ▼
# AudioOutput (back to LiveKit room)
#
# Pipecat processes data as "frames" flowing through the pipeline.
# Each processor transforms frames and passes them downstream.
#
# Key design decisions:
# - Silero VAD detects speech start/end to avoid cutting off the caller
# - STT runs in streaming mode for real-time transcription
# - LLM uses function calling to interact with the reservation backend
# - TTS generates audio chunks streamed back to the caller
# - Interruption handling: if caller speaks during TTS playback,
#   the pipeline cancels the current TTS output and processes new input


async def create_pipeline(room_name: str, restaurant_name: str) -> None:
    """Create and start the voice pipeline for a phone call.

    This function will be fully implemented once the Pipecat and LiveKit
    integrations are connected. The pipeline will:

    1. Connect to the LiveKit room as an agent participant
    2. Subscribe to the caller's audio track
    3. Run VAD -> STT -> LLM -> TTS pipeline
    4. Publish response audio back to the room
    5. Handle function calls by invoking the reservation service
    6. Manage conversation state and graceful hangup

    Args:
        room_name: LiveKit room name for this call
        restaurant_name: Name of the restaurant for greeting
    """
    logger.info("pipeline.creating", room=room_name, restaurant=restaurant_name)

    # TODO: Initialize Pipecat pipeline with:
    # - SileroVADProcessor
    # - STTProcessor (RTZR or CLOVA)
    # - LLMProcessor (ReservationLLM)
    # - TTSProcessor (CLOVA Voice)
    # - FunctionCallHandler (reservation service bridge)

    logger.info("pipeline.ready", room=room_name)
