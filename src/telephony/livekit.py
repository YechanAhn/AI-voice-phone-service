"""LiveKit server and room management utilities."""

import structlog

from src.config import settings

logger = structlog.get_logger()

# LiveKit deployment options:
#
# Option A: LiveKit Cloud (managed)
#   - Sign up at https://cloud.livekit.io
#   - Get URL, API key, and secret
#   - No infrastructure to manage
#
# Option B: Self-hosted (Docker)
#   docker run --rm \
#     -p 7880:7880 \
#     -p 7881:7881 \
#     -p 7882:7882/udp \
#     -e LIVEKIT_KEYS="devkey: secret" \
#     livekit/livekit-server
#
# SIP bridge must be deployed alongside the LiveKit server:
#   docker run --rm \
#     -e LIVEKIT_URL=ws://livekit:7880 \
#     -e LIVEKIT_API_KEY=devkey \
#     -e LIVEKIT_API_SECRET=secret \
#     -e SIP_PORT=5060 \
#     -p 5060:5060/udp \
#     livekit/sip


def get_livekit_config() -> dict:
    """Return LiveKit connection configuration."""
    return {
        "url": settings.livekit_url,
        "api_key": settings.livekit_api_key,
        "api_secret": settings.livekit_api_secret,
    }
