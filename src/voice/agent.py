"""LiveKit Agent entry point for handling inbound phone calls."""

import structlog

logger = structlog.get_logger()

# LiveKit Agent Architecture:
#
# 1. Agent registers with LiveKit server via Worker
# 2. When an inbound SIP call arrives:
#    - LiveKit creates a Room
#    - SIP bridge adds the caller as a participant
#    - Agent is dispatched to the room
# 3. Agent creates a Pipecat pipeline for voice processing
# 4. When the call ends, agent cleans up and exits the room
#
# Deployment:
#   python -m src.voice.agent
#
# This will start the agent worker that listens for new calls.


async def entrypoint(room_name: str) -> None:
    """Agent entrypoint - called when a new call arrives.

    Args:
        room_name: The LiveKit room name for this call session
    """
    logger.info("agent.entrypoint", room=room_name)

    # TODO: Full implementation with LiveKit agents SDK
    # 1. Connect to room
    # 2. Wait for SIP participant
    # 3. Create and run voice pipeline
    # 4. Handle disconnect/hangup

    from src.voice.pipeline import create_pipeline

    await create_pipeline(room_name=room_name, restaurant_name="맛있는 식당")


if __name__ == "__main__":
    # Start the LiveKit agent worker
    # In production: livekit-agents start src.voice.agent
    logger.info("agent.starting")
    print("AI Voice Phone Agent - Starting...")
    print("Waiting for inbound calls via LiveKit SIP...")

    # TODO: Initialize LiveKit WorkerAgent with:
    # - entrypoint function
    # - LiveKit connection settings
    # - SIP dispatch rules
