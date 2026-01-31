# AI Voice Phone Service - 식당 예약 AI 전화 서비스

한국 식당에 전화하면 사람처럼 자연스러운 AI 음성으로 예약, 변경, 취소를 처리하는 서비스입니다.
네이버 예약 및 캐치테이블과 연동되어 실시간으로 예약 현황을 관리합니다.

## Architecture Overview

```
고객 전화 (PSTN)
       │
       ▼
SIP Trunk (Telnyx - 070 번호)
       │
       ▼
LiveKit SIP Bridge (SIP ↔ WebRTC)
       │
       ▼
LiveKit Room (WebRTC Media Server)
       │
       ▼
┌─────────────────────────────┐
│   Pipecat Voice Pipeline    │
│                             │
│  ┌───────┐    ┌──────────┐  │
│  │  VAD  │───▶│   STT    │  │
│  │Silero │    │CLOVA/RTZR│  │
│  └───────┘    └────┬─────┘  │
│                    │        │
│              ┌─────▼─────┐  │
│              │    LLM    │  │
│              │ GPT-4o /  │  │
│              │HyperCLOVA │  │
│              └─────┬─────┘  │
│                    │        │
│              ┌─────▼─────┐  │
│              │    TTS    │  │
│              │CLOVA Voice│  │
│              └───────────┘  │
└─────────────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Reservation Backend       │
│                             │
│  ┌──────────┐ ┌───────────┐ │
│  │ 자체 DB  │ │  Sync     │ │
│  │PostgreSQL│◀▶│  Engine   │ │
│  └──────────┘ └─────┬─────┘ │
│                     │       │
│         ┌───────────┼───────┤
│         ▼           ▼       │
│  ┌───────────┐ ┌─────────┐  │
│  │네이버 예약│ │캐치테이블│  │
│  │Partner API│ │  B2B API │  │
│  └───────────┘ └─────────┘  │
└─────────────────────────────┘
```

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| **Telephony** | Telnyx SIP Trunk (070) | 한국 번호 지원, LiveKit 공식 연동 |
| **Media Server** | LiveKit (self-hosted) | SIP↔WebRTC 브릿지, 오픈소스 |
| **Voice Pipeline** | Pipecat | 프레임 기반 파이프라인, 벤더 무관 |
| **VAD** | Silero VAD | 경량, 정확한 음성 구간 감지 |
| **STT** | Return Zero (RTZR) / CLOVA Speech | 한국어 최고 정확도 (CER 5.9~8.1%) |
| **LLM** | GPT-4o (function calling) | 예약 CRUD, 한국어 대화 |
| **TTS** | Naver CLOVA Voice | 60+ 한국어 음성, 자연스러운 억양 |
| **Backend** | FastAPI (Python) | 비동기, 고성능 |
| **Database** | PostgreSQL | 예약 데이터 관리 |
| **Cache** | Redis | 세션, 실시간 상태 |
| **Deployment** | Docker Compose | 로컬/클라우드 배포 |

## Project Structure

```
AI-voice-phone-service/
├── src/
│   ├── voice/                  # Voice AI Pipeline
│   │   ├── agent.py            # LiveKit Agent entry point
│   │   ├── pipeline.py         # Pipecat pipeline configuration
│   │   ├── stt.py              # STT provider integration
│   │   ├── tts.py              # TTS provider integration
│   │   ├── llm.py              # LLM conversation handler
│   │   └── prompts/
│   │       └── system.py       # Korean restaurant reservation prompts
│   │
│   ├── reservation/            # Reservation Management
│   │   ├── models.py           # Database models
│   │   ├── service.py          # Business logic
│   │   ├── schemas.py          # Pydantic schemas
│   │   └── router.py           # API endpoints
│   │
│   ├── sync/                   # External Platform Sync
│   │   ├── naver.py            # Naver Booking sync
│   │   ├── catchtable.py       # CatchTable sync
│   │   └── base.py             # Sync interface
│   │
│   ├── telephony/              # Phone/SIP Configuration
│   │   ├── sip.py              # SIP trunk configuration
│   │   └── livekit.py          # LiveKit room management
│   │
│   └── config.py               # Application configuration
│
├── tests/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd AI-voice-phone-service
cp .env.example .env
# Edit .env with your API keys

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Run with Docker
docker compose -f docker/docker-compose.yml up

# 4. Or run locally
python -m src.voice.agent
```

## Configuration

See `.env.example` for all required environment variables.

## License

MIT
