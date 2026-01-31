"""SIP trunk configuration for Korean telephony.

Telnyx is the recommended SIP trunk provider for Korean 070 numbers.
Docs: https://developers.telnyx.com/docs/voice/sip-trunking/livekit-configuration-guide

Setup steps:
1. Create a Telnyx account and get a Korean 070 DID number
2. Required documents for Korean numbers:
   - Korean company registration certificate (사업자등록증)
   - Local passport/ID copy
   - Proof of address (3 months)
   - Local application form
3. Configure SIP trunk in Telnyx Mission Control
4. Point the trunk to your LiveKit SIP endpoint
5. Configure LiveKit inbound trunk to accept calls from Telnyx
"""

# Telnyx SIP Configuration
TELNYX_SIP_CONFIG = {
    # Telnyx SIP signaling addresses
    "signaling_addresses": [
        "sip.telnyx.com",
    ],
    # Telnyx media IP ranges (for firewall rules)
    # See: https://support.telnyx.com/en/articles/4730580-telnyx-media-ips
    "media_ip_ranges": [
        "192.76.120.0/22",
    ],
    # Audio codecs supported (in priority order)
    "codecs": [
        "PCMU",   # G.711 μ-law (8kHz, telephony standard)
        "PCMA",   # G.711 A-law
        "opus",   # Opus (higher quality if supported)
    ],
    # DTMF method
    "dtmf_type": "rfc2833",
}

# LiveKit SIP Inbound Trunk Configuration
# This is the configuration that tells LiveKit how to accept calls from Telnyx.
# Apply via: lk sip inbound create inbound-trunk.json
LIVEKIT_INBOUND_TRUNK = {
    "trunk": {
        "name": "Telnyx Korea Inbound",
        # Telnyx SIP signaling IPs (for authentication)
        "allowed_addresses": [
            "sip.telnyx.com",
        ],
        # Numbers that this trunk handles
        "allowed_numbers": [
            # Your Telnyx Korean 070 number
            # "+8270XXXXXXXX"
        ],
    }
}

# LiveKit SIP Dispatch Rule Configuration
# Routes incoming calls to the AI agent.
# Apply via: lk sip dispatch create dispatch-rule.json
LIVEKIT_DISPATCH_RULE = {
    "rule": {
        "dispatchRuleIndividual": {
            "roomPrefix": "call-",
        },
        # Only dispatch calls to these trunk IDs
        "trunkIds": [],
    }
}
