"""LiveKit Agent: handles inbound phone calls via SIP.

This is the main entry point for the voice AI service.
It registers as a LiveKit agent worker, and when an inbound
SIP call arrives, it:
1. Joins the LiveKit room
2. Waits for the SIP caller participant
3. Creates a VoicePipeline
4. Processes audio in real-time until the call ends

Run with:
    python -m src.voice.agent
"""

import asyncio
import signal

import structlog
from livekit import api, rtc

from src.config import settings
from src.voice.pipeline import VoicePipeline

logger = structlog.get_logger()


async def handle_call(room: rtc.Room, restaurant_name: str) -> None:
    """Handle a single phone call in a LiveKit room.

    Waits for the SIP participant to join, creates a voice pipeline,
    and processes audio until the call ends.
    """
    call_id = room.name
    logger.info("agent.call_started", call_id=call_id)

    pipeline = VoicePipeline(
        room=room,
        restaurant_name=restaurant_name,
    )

    # Track the SIP caller participant
    caller_identity: str | None = None
    audio_stream: rtc.AudioStream | None = None

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        nonlocal caller_identity, audio_stream
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            caller_identity = participant.identity
            audio_stream = rtc.AudioStream(track)
            logger.info(
                "agent.caller_connected",
                caller=caller_identity,
                call_id=call_id,
            )

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        if participant.identity == caller_identity:
            logger.info("agent.caller_disconnected", caller=caller_identity)
            pipeline._running = False

    # Start the voice pipeline
    await pipeline.start()

    # Wait briefly for the caller track to be subscribed
    for _ in range(50):  # Wait up to 5 seconds
        if audio_stream is not None:
            break
        await asyncio.sleep(0.1)

    if audio_stream is None:
        logger.warning("agent.no_caller_audio", call_id=call_id)
        await pipeline.stop()
        return

    # Main audio processing loop
    try:
        async for frame_event in audio_stream:
            if not pipeline._running:
                break
            await pipeline.handle_audio_frame(frame_event.frame)
    except Exception:
        logger.exception("agent.audio_loop_error")
    finally:
        await pipeline.stop()
        logger.info("agent.call_ended", call_id=call_id)


async def run_agent() -> None:
    """Run the LiveKit agent worker.

    Connects to the LiveKit server and dispatches calls
    to the handle_call function.
    """
    restaurant_name = settings.restaurant_name

    logger.info(
        "agent.starting",
        livekit_url=settings.livekit_url,
        restaurant=restaurant_name,
    )

    # Create LiveKit API client for SIP dispatch
    lk_api = api.LiveKitAPI(
        settings.livekit_url.replace("ws://", "http://").replace("wss://", "https://"),
        settings.livekit_api_key,
        settings.livekit_api_secret,
    )

    # Create the SIP inbound trunk and dispatch rule
    # (These are idempotent - safe to call on every startup)
    try:
        await lk_api.sip.create_sip_inbound_trunk(
            api.CreateSIPInboundTrunkRequest(
                trunk=api.SIPInboundTrunkInfo(
                    name="Telnyx Korea Inbound",
                    numbers=[settings.telnyx_phone_number],
                    allowed_addresses=["sip.telnyx.com"],
                )
            )
        )
        await lk_api.sip.create_sip_dispatch_rule(
            api.CreateSIPDispatchRuleRequest(
                rule=api.SIPDispatchRule(
                    dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                        room_prefix="call-",
                    )
                ),
            )
        )
        logger.info("agent.sip_configured")
    except Exception:
        logger.warning("agent.sip_config_skipped", exc_info=True)

    # Listen for new rooms (triggered by inbound SIP calls)
    room_service = lk_api.room

    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("agent.shutdown_signal")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info("agent.ready", message="Waiting for inbound calls...")

    # Poll for new rooms with call- prefix
    active_rooms: set[str] = set()
    while not shutdown_event.is_set():
        try:
            rooms_resp = await room_service.list_rooms(api.ListRoomsRequest())
            for room_info in rooms_resp.rooms:
                if (
                    room_info.name.startswith("call-")
                    and room_info.name not in active_rooms
                ):
                    active_rooms.add(room_info.name)
                    asyncio.create_task(_join_and_handle(room_info.name, restaurant_name))
        except Exception:
            logger.exception("agent.poll_error")

        await asyncio.sleep(1)

    # Cleanup
    await lk_api.aclose()
    logger.info("agent.stopped")


async def _join_and_handle(room_name: str, restaurant_name: str) -> None:
    """Join a LiveKit room and handle the call."""
    room = rtc.Room()
    try:
        await room.connect(
            settings.livekit_url,
            generate_token(room_name, "ai-agent"),
        )
        await handle_call(room, restaurant_name)
    except Exception:
        logger.exception("agent.handle_error", room=room_name)
    finally:
        await room.disconnect()


def generate_token(room_name: str, identity: str) -> str:
    """Generate a LiveKit access token for the agent to join a room."""
    token = api.AccessToken(
        settings.livekit_api_key,
        settings.livekit_api_secret,
    )
    token.with_identity(identity)
    token.with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )
    )
    return token.to_jwt()


if __name__ == "__main__":
    asyncio.run(run_agent())
