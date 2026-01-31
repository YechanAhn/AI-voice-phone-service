"""System prompts for the Voice IVR (natural voice menu) system.

The IVR system is a simpler, faster alternative to the full reservation AI.
Instead of "1번을 누르세요", the AI naturally listens and routes the caller
to the right information or action.
"""

IVR_SYSTEM_PROMPT = """당신은 [식당 이름]의 AI 전화 안내 도우미입니다.
자연스럽고 빠른 한국어 존댓말(해요체)로 응대합니다.

## 역할
- 전화를 받아 고객의 의도를 파악하고 빠르게 안내합니다
- 버튼을 누르는 ARS가 아니라, 자연스러운 음성 대화로 안내합니다
- 간단한 문의는 즉시 답변하고, 예약은 예약 전담 AI로 연결합니다

## 응대 규칙
1. 항상 존댓말(해요체)을 사용합니다
2. 답변은 2~3문장 이내로 짧고 빠르게 합니다
3. 모르는 정보는 "잠시만요, 직원 연결해 드릴게요"로 대응합니다
4. 자연스럽게, 하지만 빠르게 응대합니다 — 고객을 기다리게 하지 않습니다

## 통화 시작 인사
"안녕하세요, [식당 이름]입니다. 무엇을 도와드릴까요?"

## 안내 가능 항목
다음 항목에 대해 즉시 안내할 수 있습니다:

[메뉴 항목]

## 예약 요청 시
고객이 예약, 예약 변경, 예약 취소를 원하면:
→ "네, 예약 도와드릴게요. 예약 담당으로 바로 연결해 드리겠습니다."
→ transfer_to_reservation 함수를 호출합니다

## 직원 연결 요청 시
고객이 직접 직원과 통화를 원하면:
→ "네, 담당 직원에게 연결해 드릴게요. 잠시만 기다려 주세요."
→ transfer_to_staff 함수를 호출합니다

## 종료
안내가 끝나면:
→ "더 궁금한 점 있으시면 말씀해 주세요."
→ 고객이 "없어요", "감사합니다" 등을 말하면:
→ "감사합니다. 좋은 하루 보내세요!"
"""

IVR_FUNCTION_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "provide_info",
            "description": "식당 정보를 고객에게 안내합니다 (영업시간, 위치, 주차 등)",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "안내 카테고리",
                        "enum": [
                            "hours",
                            "location",
                            "parking",
                            "menu",
                            "private_room",
                            "corkage",
                            "kids",
                            "pets",
                            "custom",
                        ],
                    },
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_reservation",
            "description": "예약 전담 AI로 전환합니다 (예약, 변경, 취소, 조회)",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "전환 사유 (reservation, modify, cancel, lookup)",
                    },
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_staff",
            "description": "식당 직원에게 전화를 연결합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "직원 연결 사유",
                    },
                },
                "required": [],
            },
        },
    },
]

# Default menu items template - restaurants customize these
DEFAULT_MENU_ITEMS = {
    "hours": {
        "label": "영업시간",
        "keywords": ["영업시간", "몇시", "언제", "오픈", "마감", "휴무", "쉬는 날", "문 여는", "문 닫는"],
        "response": "영업시간은 매일 오전 11시 30분부터 오후 10시까지예요. 라스트 오더는 9시 반이고요. 매주 월요일은 휴무입니다.",
    },
    "location": {
        "label": "위치/오시는 길",
        "keywords": ["어디", "위치", "주소", "오시는", "찾아가", "길", "어떻게 가"],
        "response": "저희 식당은 서울시 강남구 역삼동에 위치하고 있어요. 강남역 3번 출구에서 도보 5분 거리입니다.",
    },
    "parking": {
        "label": "주차",
        "keywords": ["주차", "차", "발렛", "주차장", "파킹"],
        "response": "건물 지하 주차장 이용 가능하시고요, 2시간 무료 주차 가능합니다. 발렛 서비스는 따로 없어요.",
    },
    "menu": {
        "label": "메뉴/가격",
        "keywords": ["메뉴", "가격", "얼마", "뭐 있", "추천", "시그니처", "대표", "인기"],
        "response": "대표 메뉴는 한우 불고기 정식 2만5천원, 갈비찜 3만원이에요. 자세한 메뉴는 네이버에서 확인하실 수 있어요.",
    },
    "private_room": {
        "label": "개인실/단체석",
        "keywords": ["개인실", "룸", "단체", "프라이빗", "별도", "방"],
        "response": "8인 이상 이용 가능한 개인실이 2개 있어요. 개인실은 예약 시 미리 말씀해 주시면 준비해 드려요.",
    },
    "corkage": {
        "label": "콜키지",
        "keywords": ["콜키지", "와인", "술", "주류", "가져가도", "반입"],
        "response": "콜키지는 병당 2만원이에요. 미리 말씀해 주시면 와인잔 준비해 드릴게요.",
    },
    "kids": {
        "label": "아이/유아",
        "keywords": ["아이", "아기", "유아", "키즈", "어린이", "아이 의자", "유모차"],
        "response": "아이 의자와 아이 식기 준비되어 있어요. 유모차는 입구에 보관 가능하세요.",
    },
    "pets": {
        "label": "반려동물",
        "keywords": ["강아지", "반려동물", "애완", "펫", "개", "고양이", "동물"],
        "response": "죄송하지만 실내에는 반려동물 동반이 어려워요. 양해 부탁드려요.",
    },
}
