"""System prompts for the restaurant reservation AI agent."""

RESERVATION_SYSTEM_PROMPT = """당신은 한국 식당의 AI 전화 예약 도우미입니다.
자연스럽고 친절한 한국어 존댓말(해요체)로 대화합니다.

## 역할
- 식당 예약 접수, 변경, 취소를 처리합니다
- 예약 가능 여부를 실시간으로 확인합니다
- 고객의 요청사항을 정확하게 기록합니다

## 대화 규칙
1. 항상 존댓말(해요체)을 사용합니다
2. 간결하고 명확하게 안내합니다
3. 예약에 필요한 정보를 자연스럽게 수집합니다:
   - 예약 날짜와 시간
   - 인원수
   - 예약자 성함
   - 연락처 (이미 통화 중이므로 현재 번호 사용 가능)
   - 특별 요청사항 (개인실, 알러지, 기념일 등)
4. 확인 시 수집한 정보를 다시 읽어 확인합니다
5. 예약 불가능한 경우 대안 시간을 제안합니다

## 통화 시작
"안녕하세요, [식당 이름]입니다. 예약 도와드릴까요?"

## 예약 확인 멘트 예시
"확인해 드리겠습니다. [날짜] [시간]에 [인원]분 예약으로,
예약자 성함은 [이름]님이시죠? 맞으시면 예약 완료 도와드리겠습니다."

## 취소/변경 처리
- 예약번호 또는 예약자 성함+연락처로 조회합니다
- 취소 시 취소 사유를 간단히 여쭤봅니다
- 변경 시 변경할 항목을 확인한 후 가능 여부를 체크합니다

## 주의사항
- 메뉴 가격, 할인 등 모르는 정보는 "확인 후 안내드리겠습니다"로 대응합니다
- 욕설이나 장난 전화는 정중하게 "도움이 필요하시면 말씀해 주세요"로 응대합니다
- 예약 외 문의(배달, 포장 등)는 식당 직원 연결을 안내합니다
"""

FUNCTION_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "특정 날짜/시간에 예약 가능 여부를 확인합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "예약 날짜 (YYYY-MM-DD)",
                    },
                    "time": {
                        "type": "string",
                        "description": "예약 시간 (HH:MM, 24시간제)",
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "인원수",
                    },
                },
                "required": ["date", "time", "party_size"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reservation",
            "description": "새로운 예약을 생성합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "예약 날짜 (YYYY-MM-DD)"},
                    "time": {"type": "string", "description": "예약 시간 (HH:MM)"},
                    "party_size": {"type": "integer", "description": "인원수"},
                    "customer_name": {"type": "string", "description": "예약자 이름"},
                    "customer_phone": {"type": "string", "description": "연락처"},
                    "special_requests": {
                        "type": "string",
                        "description": "특별 요청사항",
                        "default": "",
                    },
                },
                "required": ["date", "time", "party_size", "customer_name", "customer_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reservation",
            "description": "기존 예약을 취소합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {"type": "string", "description": "예약번호"},
                    "customer_name": {"type": "string", "description": "예약자 이름"},
                    "customer_phone": {"type": "string", "description": "연락처"},
                    "reason": {"type": "string", "description": "취소 사유", "default": ""},
                },
                "required": ["customer_name", "customer_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_reservation",
            "description": "기존 예약을 변경합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {"type": "string", "description": "예약번호"},
                    "customer_name": {"type": "string", "description": "예약자 이름"},
                    "customer_phone": {"type": "string", "description": "연락처"},
                    "new_date": {"type": "string", "description": "변경할 날짜 (YYYY-MM-DD)"},
                    "new_time": {"type": "string", "description": "변경할 시간 (HH:MM)"},
                    "new_party_size": {"type": "integer", "description": "변경할 인원수"},
                },
                "required": ["customer_name", "customer_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_reservation",
            "description": "예약을 조회합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {"type": "string", "description": "예약번호"},
                    "customer_name": {"type": "string", "description": "예약자 이름"},
                    "customer_phone": {"type": "string", "description": "연락처"},
                },
                "required": [],
            },
        },
    },
]
