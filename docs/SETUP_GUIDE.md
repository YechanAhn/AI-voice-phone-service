# 셋업 가이드: AI 음성 식당 예약 서비스 테스트

## 테스트 단계별 로드맵

```
Phase 1: 유닛 테스트 (API 키 불필요)       ← 지금 바로 가능
Phase 2: LLM 대화 테스트 (OpenAI만)        ← OpenAI 키 1개
Phase 3: IVR 음성메뉴 테스트               ← OpenAI 키 1개 (선택)
Phase 4: 음성 통합 테스트 (STT+TTS)         ← RTZR + CLOVA 키
Phase 5: 전화 E2E 테스트 (SIP 연결)         ← Telnyx + LiveKit
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
# 전체 실행 (108개 테스트)
python -m pytest tests/ -v

# 커버리지 포함
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# 개별 모듈 테스트
python -m pytest tests/test_ivr.py -v             # IVR 음성메뉴 (47개)
python -m pytest tests/test_tts.py -v             # TTS 문장분할, WAV변환
python -m pytest tests/test_stt.py -v             # STT 설정, 팩토리
python -m pytest tests/test_llm.py -v             # LLM 프롬프트, function calling
python -m pytest tests/test_reservation_service.py -v  # 예약 CRUD
python -m pytest tests/test_sync.py -v            # 동기화 안전모드
```

### 1-3. 예상 결과

```
108 passed in ~5s
```

모두 통과하면 코드 로직은 정상입니다. 외부 API 키 없이 여기까지 가능.

---

## Phase 2: LLM 대화 테스트 (OpenAI API 키 필요)

실제 GPT-4o와 대화하며 예약 시나리오를 테스트합니다.

### 2-1. API 키 발급

1. https://platform.openai.com/ 가입
2. API Keys > Create new secret key
3. 잔액 충전 ($5~10이면 테스트 충분)

### 2-2. 환경변수 설정

```bash
# .env 파일 생성 (없으면)
cat > .env << 'EOF'
OPENAI_API_KEY=sk-proj-...실제키...
LLM_MODEL=gpt-4o
RESTAURANT_NAME=맛있는 한식당
EOF
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

### 2-4. 확인 포인트

- [ ] AI가 존댓말(해요체)로 응답하는지
- [ ] 예약 요청 시 `check_availability` function call이 발생하는지
- [ ] 가용성 결과 제공 후 이름/연락처 수집을 자연스럽게 하는지
- [ ] 취소/변경 시나리오도 테스트

---

## Phase 3: IVR 음성메뉴 테스트

IVR은 전체 AI 예약보다 단순한 서비스입니다. LLM 없이도 키워드 매칭으로 대부분 동작합니다.

### 3-1. 키워드 매칭 테스트 (API 키 불필요)

```bash
python -c "
import asyncio
from src.voice.ivr import VoiceIVR, IVRConfig

async def test():
    config = IVRConfig(restaurant_name='서울 한식당')
    ivr = VoiceIVR(config=config)

    print('=== IVR 음성메뉴 테스트 ===')
    print(f'인사말: {ivr.greeting}')
    print(f'안내 항목: {ivr.menu_summary}')
    print()

    # FAQ 테스트 (키워드 매칭 — LLM 안 씀, 즉시 응답)
    tests = [
        '영업시간이 어떻게 되나요?',
        '주차 가능한가요?',
        '위치가 어디예요?',
        '메뉴 추천해주세요',
        '개인실 있나요?',
        '콜키지 되나요?',
        '아이 의자 있어요?',
        '반려동물 가능한가요?',
    ]

    for q in tests:
        r = await ivr.process_utterance(q)
        print(f'Q: {q}')
        print(f'A: {r[\"text\"]}')
        print(f'   action={r[\"action\"]}, done={r[\"done\"]}')
        print()

    # 예약 전환 테스트
    r = await ivr.process_utterance('예약하고 싶은데요')
    print(f'Q: 예약하고 싶은데요')
    print(f'A: {r[\"text\"]}')
    print(f'   action={r[\"action\"]}  ← transfer_reservation이면 정상')
    print()

    # 직원 연결 테스트
    r = await ivr.process_utterance('직원 연결해주세요')
    print(f'Q: 직원 연결해주세요')
    print(f'A: {r[\"text\"]}')
    print(f'   action={r[\"action\"]}  ← transfer_staff이면 정상')
    print()

    # 종료 테스트
    r = await ivr.process_utterance('감사합니다')
    print(f'Q: 감사합니다')
    print(f'A: {r[\"text\"]}')
    print(f'   action={r[\"action\"]}, done={r[\"done\"]}  ← done=True이면 정상')

asyncio.run(test())
"
```

### 3-2. LLM 폴백 테스트 (OpenAI 키 필요)

키워드에 매칭 안 되는 질문은 GPT-4o-mini로 처리됩니다.

```bash
python -c "
import asyncio
from src.voice.ivr import VoiceIVR, IVRConfig

async def test():
    ivr = VoiceIVR(config=IVRConfig(restaurant_name='서울 한식당'))

    # 키워드에 없는 질문 → LLM 폴백
    questions = [
        '오늘 특별 메뉴가 뭐예요?',
        '생일 파티 가능한가요?',
        '와이파이 비밀번호가 뭐예요?',
    ]

    for q in questions:
        r = await ivr.process_utterance(q)
        print(f'Q: {q}')
        print(f'A: {r[\"text\"]}')
        print(f'   action={r[\"action\"]}')
        print()

asyncio.run(test())
"
```

### 3-3. 식당별 커스텀 테스트

실제 식당에 맞게 메뉴 항목을 커스텀하는 예시:

```bash
python -c "
import asyncio
from src.voice.ivr import VoiceIVR, IVRConfig, MenuItem

async def test():
    config = IVRConfig(
        restaurant_name='강남 스시오마카세',
        greeting='안녕하세요, 강남 스시오마카세입니다. 무엇을 도와드릴까요?',
        menu_items=[
            MenuItem(
                category='hours',
                label='영업시간',
                keywords=['영업시간', '몇시', '오픈', '마감'],
                response='점심 11시 30분부터 2시, 저녁 5시 30분부터 10시까지예요. 일요일 휴무입니다.',
            ),
            MenuItem(
                category='price',
                label='가격',
                keywords=['가격', '얼마', '코스', '오마카세'],
                response='런치 오마카세 8만원, 디너 오마카세 15만원, 스페셜 코스 25만원입니다.',
            ),
            MenuItem(
                category='parking',
                label='주차',
                keywords=['주차', '발렛'],
                response='건물 B2 주차장 이용 가능하시고, 발렛은 따로 없어요. 2시간 무료입니다.',
            ),
            MenuItem(
                category='counter',
                label='카운터석',
                keywords=['카운터', '바', '좌석', '자리'],
                response='카운터 8석, 테이블 4인석 2개 있어요. 카운터석 추천드려요.',
            ),
            MenuItem(
                category='allergy',
                label='알러지',
                keywords=['알러지', '알레르기', '못 먹', '제한'],
                response='알러지가 있으시면 예약 시 미리 말씀해 주세요. 대체 재료로 준비해 드려요.',
            ),
        ],
    )

    ivr = VoiceIVR(config=config)
    print(f'인사말: {ivr.greeting}')
    print()

    for q in ['오마카세 얼마예요?', '카운터 자리 있어요?', '알러지가 있는데요']:
        r = await ivr.process_utterance(q)
        print(f'Q: {q}')
        print(f'A: {r[\"text\"]}')
        print()

asyncio.run(test())
"
```

### 3-4. 확인 포인트

- [ ] 8개 기본 FAQ 항목 모두 즉시 응답하는지 (100~200ms)
- [ ] 예약 요청 시 `transfer_reservation` 액션이 반환되는지
- [ ] 직원 연결 요청 시 `transfer_staff` 액션이 반환되는지
- [ ] 키워드에 없는 질문에 LLM 폴백이 자연스럽게 작동하는지
- [ ] 커스텀 메뉴 항목이 정상 적용되는지

---

## Phase 4: 음성 통합 테스트 (STT + TTS)

실제 한국어 음성 인식과 합성을 테스트합니다.

### 4-1. API 키 발급

#### STT: Return Zero (RTZR) — 추천
1. https://developers.rtzr.ai/ 가입
2. 대시보드 > 앱 생성 > Client ID / Secret 확인
3. 무료 크레딧 제공됨

#### TTS: Naver CLOVA Voice
1. https://www.ncloud.com/ 가입
2. 콘솔 > AI·NAVER API > CLOVA Voice 신청
3. 인증키 발급 (API KEY ID + SECRET)

### 4-2. 환경변수 추가

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

### 4-3. TTS 단독 테스트

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
# Linux: mpv /tmp/test_greeting.mp3
```

### 4-4. STT 토큰 발급 테스트

```bash
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

### 4-5. STT + TTS 연결 테스트 (마이크 필요)

마이크가 있는 환경에서 음성 → 텍스트 → 음성 왕복 테스트:

```bash
pip install sounddevice numpy

python -c "
import asyncio
import numpy as np
import sounddevice as sd
from src.voice.stt import ReturnZeroSTT
from src.voice.tts import ClovaVoiceTTS

async def test():
    stt = ReturnZeroSTT()
    tts = ClovaVoiceTTS()

    # 3초간 마이크 녹음 (16kHz mono)
    print('3초간 말씀해 주세요...')
    audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype='int16')
    sd.wait()
    print('녹음 완료. STT 전송 중...')

    # STT 전송
    await stt.connect()
    pcm_bytes = audio.tobytes()
    chunk_size = 3200  # 100ms at 16kHz
    for i in range(0, len(pcm_bytes), chunk_size):
        await stt.send_audio(pcm_bytes[i:i+chunk_size])
        await asyncio.sleep(0.05)
    await stt.end_utterance()

    # 결과 수신
    text = ''
    async for t in stt.receive_transcripts():
        if t['is_final']:
            text = t['text']
            break

    print(f'인식 결과: {text}')
    await stt.close()

    if text:
        # TTS로 응답 생성
        print('TTS 합성 중...')
        mp3 = await tts.synthesize(f'방금 말씀하신 내용은: {text}', speaker='nara_call')
        with open('/tmp/stt_echo.mp3', 'wb') as f:
            f.write(mp3)
        print(f'응답 저장: /tmp/stt_echo.mp3')

    await tts.close()

asyncio.run(test())
"
```

### 4-6. 확인 포인트

- [ ] TTS: MP3 파일 재생 시 자연스러운 한국어 음성인지
- [ ] TTS: `nara_call` 음색이 콜센터 느낌인지 (vs `nara` 내레이션 느낌)
- [ ] STT: 토큰 발급 정상 동작
- [ ] STT: 한국어 인식 정확도 확인

---

## Phase 5: 전체 E2E 테스트 (전화 통화)

실제 전화를 걸어서 AI와 대화합니다.

### 5-1. 서비스 모드 선택

`.env`에서 모드 설정:
```bash
# Full AI 예약 모드 (기본값)
SERVICE_MODE=full

# 또는 IVR 음성메뉴 모드
SERVICE_MODE=ivr
IVR_ENABLE_RESERVATION_TRANSFER=true
```

### 5-2. 인프라 시작 (Docker)

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

# 로그 실시간 확인
docker compose -f docker/docker-compose.yml logs -f agent
```

### 5-3. 서비스 상태 확인

```bash
# API 헬스체크
curl http://localhost:8000/health
# → {"status":"ok","service":"ai-voice-phone-service"}

# PostgreSQL 테이블 확인
docker compose -f docker/docker-compose.yml exec postgres \
  psql -U postgres -d reservations -c '\dt'

# LiveKit 상태 확인
# lk CLI 설치: go install github.com/livekit/livekit-cli/cmd/lk@latest
lk room list --url http://localhost:7880 --api-key devkey --api-secret secret
```

### 5-4. 예약 REST API 직접 테스트

```bash
# 가용성 확인
curl -s -X POST http://localhost:8000/api/reservations/check-availability \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-14","time":"18:00","party_size":4}' | python -m json.tool

# 예약 생성
curl -s -X POST http://localhost:8000/api/reservations/create \
  -H "Content-Type: application/json" \
  -d '{
    "date":"2026-02-14",
    "time":"18:00",
    "party_size":4,
    "customer_name":"김테스트",
    "customer_phone":"010-1234-5678",
    "special_requests":"창가 자리"
  }' | python -m json.tool

# 예약 조회
curl -s -X POST http://localhost:8000/api/reservations/lookup \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"김테스트","customer_phone":"010-1234-5678"}' | python -m json.tool
```

### 5-5. SIP 소프트폰으로 로컬 테스트 (Telnyx 없이)

Telnyx 계정 없이 로컬에서 음성 통화 테스트하는 방법:

#### 방법 A: Orecx (추천, GUI 있음)

```bash
# macOS
brew install orecx

# Linux (Ubuntu)
sudo snap install orecx
# 또는 Orecx 공식 사이트에서 다운로드
```

설정:
1. SIP 계정: `test@localhost:5060` (사용자 이름만, 비밀번호 불필요)
2. SIP Proxy: `localhost:5060`
3. Transport: UDP
4. Codec: PCMU (G.711 μ-law) 또는 PCMA
5. 통화: 아무 번호로 다이얼 → LiveKit SIP Bridge가 수신

#### 방법 B: Orecx-cli (CLI, 서버 환경)

```bash
apt-get install -y linphone-cli  # Ubuntu
# 또는
brew install orecx  # macOS

# SIP 통화 시작
linphonec
> register sip:test@localhost:5060
> call sip:restaurant@localhost:5060
# 마이크로 말하면 AI가 응답
```

#### 방법 C: lk CLI로 테스트 룸 수동 생성

```bash
# 테스트 룸 생성 (agent가 자동 감지)
lk room create call-test-001 \
  --url http://localhost:7880 \
  --api-key devkey \
  --api-secret secret

# Agent가 자동으로 룸에 참가하는지 로그 확인
docker compose -f docker/docker-compose.yml logs -f agent
# → "agent.call_started, call_id=call-test-001, mode=full" (또는 mode=ivr)
```

#### 방법 D: WebRTC 테스트 페이지

```bash
# LiveKit Playground에서 브라우저로 직접 접속
# https://meet.livekit.io 에서:
#   - URL: ws://localhost:7880
#   - Token: (아래 명령으로 생성)

lk token create \
  --api-key devkey \
  --api-secret secret \
  --room call-test-001 \
  --identity caller \
  --join
```

### 5-6. Telnyx 전화 테스트 (실제 전화번호)

#### Telnyx 설정
1. https://telnyx.com 가입
2. Mission Control > SIP Trunking > Create
3. 한국 070 번호 주문 (사업자등록증 필요)
4. SIP Trunk Termination URI를 서버 IP로 설정:
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
4. AI 인사: "안녕하세요, 맛있는 식당입니다."
   - full 모드: "예약 도와드릴까요?"
   - ivr 모드: "무엇을 도와드릴까요?"
5. 실시간 대화 시작
```

---

## 비용 참고

| 서비스 | 무료 티어 | 테스트 예상 비용 |
|--------|----------|----------------|
| **OpenAI GPT-4o** | 없음 | $5~10 (수백 건 대화) |
| **OpenAI GPT-4o-mini** (IVR 폴백) | 없음 | $1~2 (수천 건) |
| **RTZR** | 가입 시 무료 크레딧 | 무료 범위 내 |
| **CLOVA Voice** | 월 90,000자 무료 | 무료 범위 내 |
| **CLOVA Speech** | 월 60분 무료 | 무료 범위 내 |
| **Telnyx 070** | 없음 | $1/월 + 통화료 |
| **LiveKit Cloud** | 50GB 무료 | 무료 범위 내 |

**Phase 1~4까지는 $5~10 이내**로 테스트 가능합니다.
Telnyx 070 번호 취득은 사업자등록증이 필요합니다.

---

## 환경변수 전체 목록 (.env 예시)

```bash
# === 필수 (Phase 2부터) ===
OPENAI_API_KEY=sk-proj-...
LLM_MODEL=gpt-4o

# === 식당 정보 ===
RESTAURANT_NAME=맛있는 한식당
RESTAURANT_ID=1

# === 서비스 모드 ===
# "full" = AI 예약 처리  |  "ivr" = 자연스러운 음성 메뉴
SERVICE_MODE=full
IVR_ENABLE_RESERVATION_TRANSFER=true
IVR_STAFF_TRANSFER_NUMBER=

# === STT (Phase 4부터) ===
RTZR_CLIENT_ID=
RTZR_CLIENT_SECRET=

# === TTS (Phase 4부터) ===
CLOVA_VOICE_CLIENT_ID=
CLOVA_VOICE_CLIENT_SECRET=
CLOVA_VOICE_SPEAKER=nara_call

# === 인프라 (Phase 5) ===
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/reservations
REDIS_URL=redis://localhost:6379/0

# === 전화 (Phase 5) ===
TELNYX_API_KEY=
TELNYX_SIP_TRUNK_ID=
TELNYX_PHONE_NUMBER=

# === 플랫폼 동기화 (선택) ===
NAVER_BOOKING_CLIENT_ID=
NAVER_BOOKING_CLIENT_SECRET=
NAVER_BUSINESS_ID=
CATCHTABLE_API_KEY=
CATCHTABLE_RESTAURANT_ID=
```

---

## 트러블슈팅

### pytest import 실패
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

### IVR 모드에서 예약 핸드오프 안 될 때
```bash
# .env에 다음 설정 확인
SERVICE_MODE=ivr
IVR_ENABLE_RESERVATION_TRANSFER=true

# 로그에서 핸드오프 확인
docker compose -f docker/docker-compose.yml logs -f agent | grep handoff
```

### Agent가 통화 감지 못 할 때
```bash
# LiveKit 룸 목록 확인
lk room list --url http://localhost:7880 --api-key devkey --api-secret secret

# 룸 이름이 "call-"로 시작해야 Agent가 감지함
# Agent 로그 확인
docker compose -f docker/docker-compose.yml logs -f agent
```
