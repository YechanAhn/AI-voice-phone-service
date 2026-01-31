# 셋업 가이드: AI 음성 식당 예약 서비스 테스트

## 테스트 단계별 로드맵

```
Phase 1: 유닛 테스트 (API 키 불필요)       ← 지금 바로 가능
Phase 2: LLM 통합 테스트 (OpenAI만)        ← OpenAI 키 1개
Phase 3: 음성 통합 테스트 (STT+TTS)         ← RTZR + CLOVA 키
Phase 4: 전화 E2E 테스트 (SIP 연결)         ← Telnyx + LiveKit
```

---

## Phase 1: 유닛 테스트 (지금 바로 가능)

외부 서비스 없이 로직만 테스트합니다.

### 1-1. 의존성 설치

```bash
# Python 3.11 이상 필요
python --version  # 3.11+

# 프로젝트 의존성 + 테스트 도구 + SQLite 드라이버
pip install -e ".[dev]" aiosqlite
```

### 1-2. 유닛 테스트 실행

```bash
# 전체 실행 (61개 테스트)
python -m pytest tests/ -v

# 커버리지 포함
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# 개별 모듈 테스트
python -m pytest tests/test_tts.py -v            # TTS 문장분할, WAV변환
python -m pytest tests/test_stt.py -v            # STT 설정, 팩토리
python -m pytest tests/test_llm.py -v            # LLM 프롬프트, function calling
python -m pytest tests/test_reservation_service.py -v  # 예약 CRUD
python -m pytest tests/test_sync.py -v           # 동기화 안전모드
```

### 1-3. 린트/타입체크

```bash
ruff check src/
# mypy는 livekit 등 외부 패키지 스텁이 없어서 --ignore-missing-imports 필요
mypy src/ --ignore-missing-imports
```

---

## Phase 2: LLM 대화 테스트 (OpenAI API 키 필요)

실제 GPT-4o와 대화하며 예약 시나리오를 테스트합니다.

### 2-1. API 키 발급

1. https://platform.openai.com/ 가입
2. API Keys > Create new secret key
3. 잔액 충전 ($5~10이면 테스트 충분)

### 2-2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 입력:
```
OPENAI_API_KEY=sk-proj-...실제키...
LLM_MODEL=gpt-4o
```

### 2-3. 대화 테스트 스크립트

```bash
python -c "
import asyncio
from src.voice.llm import ReservationLLM

async def test():
    llm = ReservationLLM(restaurant_name='맛있는 한식당')

    # 시나리오 1: 예약
    r = await llm.process_message('안녕하세요, 예약하고 싶은데요')
    print('[AI]', r['text'])

    r = await llm.process_message('이번 주 토요일 저녁 6시에 4명이요')
    print('[AI]', r)

    # function_call이 반환되면 가짜 결과를 넣어줌
    if r.get('function_call'):
        fc = r['function_call']
        print('[Function]', fc['name'], fc['arguments'])
        r = await llm.provide_function_result(
            fc['id'],
            '{\"available\": true, \"remaining_capacity\": 16}'
        )
        print('[AI]', r['text'])

asyncio.run(test())
"
```

---

## Phase 3: 음성 통합 테스트 (STT + TTS)

실제 한국어 음성 인식과 합성을 테스트합니다.

### 3-1. API 키 발급

#### STT: Return Zero (RTZR) — 추천
1. https://developers.rtzr.ai/ 가입
2. 대시보드 > 앱 생성 > Client ID / Secret 확인
3. 무료 크레딧 제공됨

#### TTS: Naver CLOVA Voice
1. https://www.ncloud.com/ 가입
2. 콘솔 > AI·NAVER API > CLOVA Voice 신청
3. 인증키 발급 (API KEY ID + SECRET)

### 3-2. 환경변수 추가

`.env`에 추가:
```
# STT
RTZR_CLIENT_ID=실제_클라이언트_ID
RTZR_CLIENT_SECRET=실제_클라이언트_시크릿

# TTS
CLOVA_VOICE_CLIENT_ID=실제_API_KEY_ID
CLOVA_VOICE_CLIENT_SECRET=실제_API_KEY_SECRET
CLOVA_VOICE_SPEAKER=nara_call
```

### 3-3. TTS 단독 테스트

```bash
python -c "
import asyncio
from src.voice.tts import ClovaVoiceTTS

async def test():
    tts = ClovaVoiceTTS()

    # MP3로 합성
    audio = await tts.synthesize(
        '안녕하세요, 맛있는 식당입니다. 예약 도와드릴까요?',
        speaker='nara_call'
    )
    with open('/tmp/test_greeting.mp3', 'wb') as f:
        f.write(audio)
    print(f'MP3 저장 완료: {len(audio)} bytes -> /tmp/test_greeting.mp3')

    # PCM16 8kHz로 합성 (전화 품질)
    pcm = await tts.synthesize_pcm(
        '네, 2월 8일 토요일 저녁 6시에 4명 예약 확인되었습니다.',
        sample_rate=8000
    )
    print(f'PCM16 8kHz: {len(pcm)} bytes, {len(pcm)/16000:.1f}초')

    await tts.close()

asyncio.run(test())
"
# 생성된 MP3 파일을 재생해서 음질 확인
# macOS: afplay /tmp/test_greeting.mp3
# Linux: mpv /tmp/test_greeting.mp3 또는 aplay (WAV만)
```

### 3-4. STT 단독 테스트

```bash
# 마이크가 있는 환경에서 테스트
# 또는 WAV 파일을 PCM16 8kHz로 변환해서 전송
python -c "
import asyncio
from src.voice.stt import ReturnZeroSTT

async def test():
    stt = ReturnZeroSTT()
    token = await stt._ensure_token()
    print(f'토큰 발급 성공: {token[:20]}...')
    config = stt._streaming_config()
    print(f'스트리밍 설정: {config}')

asyncio.run(test())
"
```

---

## Phase 4: 전체 E2E 테스트 (전화 통화)

실제 전화를 걸어서 AI와 대화합니다.

### 4-1. 인프라 시작 (Docker)

```bash
# .env 파일에 모든 API 키가 설정되어 있어야 함
docker compose -f docker/docker-compose.yml up -d

# 상태 확인
docker compose -f docker/docker-compose.yml ps

# 예상 결과:
# postgres     running (healthy)
# redis        running (healthy)
# livekit      running
# livekit-sip  running
# api          running (0.0.0.0:8000)
# agent        running
```

### 4-2. 서비스 상태 확인

```bash
# API 헬스체크
curl http://localhost:8000/health
# {"status":"ok","service":"ai-voice-phone-service"}

# PostgreSQL 접속 테스트
docker compose -f docker/docker-compose.yml exec postgres psql -U postgres -d reservations -c '\dt'

# LiveKit 상태 확인
# lk CLI 필요: go install github.com/livekit/livekit-cli/cmd/lk@latest
lk room list --url http://localhost:7880 --api-key devkey --api-secret secret
```

### 4-3. 예약 API 직접 테스트

```bash
# 가용성 확인
curl -X POST http://localhost:8000/api/reservations/check-availability \
  -H "Content-Type: application/json" \
  -d '{"date":"2025-02-08","time":"18:00","party_size":4}'

# 예약 생성
curl -X POST http://localhost:8000/api/reservations/create \
  -H "Content-Type: application/json" \
  -d '{
    "date":"2025-02-08",
    "time":"18:00",
    "party_size":4,
    "customer_name":"김테스트",
    "customer_phone":"010-1234-5678",
    "special_requests":"창가 자리"
  }'

# 예약 조회
curl -X POST http://localhost:8000/api/reservations/lookup \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"김테스트","customer_phone":"010-1234-5678"}'
```

### 4-4. 전화 테스트 (Telnyx 필요)

#### Telnyx 설정
1. https://telnyx.com 가입
2. Mission Control > SIP Trunking > Create
3. 한국 070 번호 주문 (사업자등록증 필요)
4. SIP Trunk Termination URI를 LiveKit SIP 주소로 설정:
   - `sip:{YOUR_SERVER_IP}:5060`

#### .env에 Telnyx 키 추가
```
TELNYX_API_KEY=KEY_실제값
TELNYX_SIP_TRUNK_ID=트렁크_ID
TELNYX_PHONE_NUMBER=+8270XXXXXXXX
```

#### 전화 걸기
```
070-XXXX-XXXX로 전화를 걸면:
1. Telnyx가 SIP 시그널을 수신
2. LiveKit SIP Bridge가 WebRTC 룸 생성
3. Voice Agent가 룸에 참가
4. AI 인사: "안녕하세요, 맛있는 식당입니다. 예약 도와드릴까요?"
5. 실시간 대화 시작
```

### 4-5. SIP 소프트폰으로 로컬 테스트 (Telnyx 없이)

Telnyx 계정 없이 로컬에서 테스트하는 방법:

```bash
# 1. Orecx나 Opal Orecx 같은 SIP 소프트폰 설치
# 또는 Orecx SIP 클라이언트 대신 Orecx를 쓸 수 있음
# 가장 쉬운 옵션: Orecx Orecx 대신 Orecx를

# Orecx 대신 linphone-cli 사용:
apt-get install -y linphone  # 또는 brew install linphone (macOS)

# 2. LiveKit SIP로 직접 전화 (로컬)
# SIP URI: sip:test@localhost:5060

# 3. 또는 lk CLI로 테스트 룸 생성
lk room create call-test-001 \
  --url http://localhost:7880 \
  --api-key devkey \
  --api-secret secret

# Agent가 자동으로 룸에 참가하는지 로그 확인
docker compose -f docker/docker-compose.yml logs -f agent
```

---

## 비용 참고

| 서비스 | 무료 티어 | 테스트 예상 비용 |
|--------|----------|----------------|
| **OpenAI GPT-4o** | 없음 | $5~10 (수백 건 대화) |
| **RTZR** | 가입 시 무료 크레딧 | 무료 범위 내 |
| **CLOVA Voice** | 월 90,000자 무료 | 무료 범위 내 |
| **CLOVA Speech** | 월 60분 무료 | 무료 범위 내 |
| **Telnyx 070** | 없음 | $1/월 + 통화료 |
| **LiveKit Cloud** | 50GB 무료 | 무료 범위 내 |

**Phase 1~3까지는 $5~10 이내**로 테스트 가능합니다.
Telnyx 070 번호 취득은 사업자등록증이 필요해서 별도 준비가 필요합니다.

---

## 트러블슈팅

### pytest가 import 실패할 때
```bash
# src가 패키지로 인식 안 될 때
pip install -e ".[dev]"
```

### Docker postgres 연결 실패
```bash
# 포트 충돌 확인
lsof -i :5432
# 로컬 postgres가 있으면 멈추거나 docker-compose 포트 변경
```

### LiveKit SIP 연결 안 될 때
```bash
# 방화벽에서 UDP 5060, 7882 포트 열기
# Docker 네트워크 확인
docker compose -f docker/docker-compose.yml logs livekit-sip
```

### CLOVA TTS 403 에러
```bash
# NCP 콘솔에서 CLOVA Voice API 활성화 확인
# API 키 ID와 Secret이 바뀌지 않았는지 확인
# 도메인 제한 설정이 있다면 해제
```
