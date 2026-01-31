"""Voice IVR: natural voice menu system for restaurant phone calls.

A simpler, faster alternative to the full AI reservation service.
Instead of traditional "press 1 for X, press 2 for Y" IVR,
this uses natural voice interaction:

  Caller: "영업시간이 어떻게 되나요?"
  AI: "영업시간은 매일 오전 11시 30분부터 오후 10시까지예요."

  Caller: "예약하고 싶은데요"
  AI: "네, 예약 도와드릴게요. 예약 담당으로 바로 연결해 드리겠습니다."
  → Routes to full reservation AI

Key differences from the full reservation pipeline:
- Uses keyword matching FIRST for instant FAQ responses (no LLM call)
- Falls back to lightweight LLM (gpt-4o-mini) only when keywords don't match
- Pre-configured responses per restaurant (no per-turn LLM inference for FAQs)
- Sub-200ms response for known queries vs 400-900ms for LLM
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import structlog
from openai import AsyncOpenAI

from src.config import settings
from src.voice.prompts.ivr import (
    DEFAULT_MENU_ITEMS,
    IVR_FUNCTION_DEFINITIONS,
    IVR_SYSTEM_PROMPT,
)

logger = structlog.get_logger()


@dataclass
class MenuItem:
    """A single IVR menu item with keywords and a canned response."""

    category: str
    label: str
    keywords: list[str]
    response: str


@dataclass
class IVRConfig:
    """Configuration for a restaurant's Voice IVR.

    Each restaurant can customize:
    - greeting: the opening message
    - menu_items: FAQ responses for common questions
    - enable_reservation_transfer: whether to route reservation requests to AI
    - staff_transfer_number: SIP URI or extension to transfer to human staff
    """

    restaurant_name: str = "맛있는 식당"
    greeting: str = ""
    menu_items: list[MenuItem] = field(default_factory=list)
    enable_reservation_transfer: bool = True
    staff_transfer_number: str = ""

    def __post_init__(self) -> None:
        if not self.greeting:
            self.greeting = f"안녕하세요, {self.restaurant_name}입니다. 무엇을 도와드릴까요?"
        if not self.menu_items:
            self.menu_items = [
                MenuItem(
                    category=cat,
                    label=info["label"],
                    keywords=info["keywords"],
                    response=info["response"],
                )
                for cat, info in DEFAULT_MENU_ITEMS.items()
            ]


class VoiceIVR:
    """Natural voice IVR handler.

    Processing order for each utterance:
    1. Check for farewell → end call
    2. Check against FAQ keyword matching → instant canned response
    3. Check for reservation-related keywords → transfer to reservation AI
    4. Check for staff transfer keywords → transfer to staff
    5. Fall back to lightweight LLM for unmatched queries

    FAQ is checked before reservation so that "영업시간" matches the FAQ
    instead of triggering a reservation transfer via "시간".
    """

    # Keywords that indicate the caller wants reservation service.
    # Intentionally specific — "시간" and "날짜" alone are too generic
    # (e.g. "영업시간" triggers false positive).
    RESERVATION_KEYWORDS = [
        "예약", "부킹", "자리 있", "테이블", "예약 날짜", "예약 시간", "인원",
        "취소", "변경", "수정", "예약 확인", "예약 조회",
    ]

    # Keywords that indicate the caller wants human staff
    STAFF_KEYWORDS = [
        "직원", "사람", "상담원", "매니저", "사장", "연결",
        "담당자", "바꿔", "통화",
    ]

    # Keywords that indicate the conversation should end
    FAREWELL_KEYWORDS = [
        "감사합니다", "고마워요", "없어요", "괜찮아요", "됐어요",
        "안녕히", "끊을게요", "바이",
    ]

    def __init__(self, config: IVRConfig | None = None) -> None:
        self.config = config or IVRConfig(restaurant_name=settings.restaurant_name)
        self._llm_client: AsyncOpenAI | None = None
        self._messages: list[dict] = []
        self._build_system_prompt()

    def _build_system_prompt(self) -> None:
        """Build the system prompt with restaurant-specific menu items."""
        menu_section = "\n".join(
            f"- **{item.label}**: {item.response}"
            for item in self.config.menu_items
        )
        prompt = IVR_SYSTEM_PROMPT.replace(
            "[식당 이름]", self.config.restaurant_name
        ).replace(
            "[메뉴 항목]", menu_section
        )
        self._messages = [{"role": "system", "content": prompt}]

    def _match_keywords(self, text: str, keywords: list[str]) -> bool:
        """Check if any keyword appears in the text."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def _find_menu_match(self, text: str) -> MenuItem | None:
        """Find a matching menu item by keyword search."""
        text_lower = text.lower()
        best_match: MenuItem | None = None
        best_count = 0
        for item in self.config.menu_items:
            count = sum(1 for kw in item.keywords if kw in text_lower)
            if count > best_count:
                best_count = count
                best_match = item
        return best_match

    async def process_utterance(self, text: str) -> dict:
        """Process a caller's utterance and return the IVR response.

        Returns:
            dict with keys:
                - "text": response text to speak via TTS (str | None)
                - "action": one of "respond", "transfer_reservation",
                            "transfer_staff", "end"
                - "done": whether the call should end (bool)
        """
        text = text.strip()
        if not text:
            return {
                "text": "죄송해요, 잘 못 들었어요. 다시 말씀해 주시겠어요?",
                "action": "respond",
                "done": False,
            }

        logger.info("ivr.processing", text=text[:80])

        # 1. Farewell detection
        if self._match_keywords(text, self.FAREWELL_KEYWORDS):
            return {
                "text": "감사합니다. 좋은 하루 보내세요!",
                "action": "end",
                "done": True,
            }

        # 2. FAQ keyword matching (instant, no LLM — checked first for speed)
        menu_match = self._find_menu_match(text)
        if menu_match:
            logger.info("ivr.faq_match", category=menu_match.category)
            return {
                "text": menu_match.response,
                "action": "respond",
                "done": False,
            }

        # 3. Reservation intent → transfer
        if self._match_keywords(text, self.RESERVATION_KEYWORDS):
            if self.config.enable_reservation_transfer:
                return {
                    "text": "네, 예약 도와드릴게요. 예약 담당으로 바로 연결해 드리겠습니다.",
                    "action": "transfer_reservation",
                    "done": False,
                }
            return {
                "text": "예약은 네이버 예약이나 캐치테이블에서 가능해요. "
                        "또는 잠시 후 직원이 연결해 드릴게요.",
                "action": "transfer_staff",
                "done": False,
            }

        # 4. Staff transfer request
        if self._match_keywords(text, self.STAFF_KEYWORDS):
            return {
                "text": "네, 담당 직원에게 연결해 드릴게요. 잠시만 기다려 주세요.",
                "action": "transfer_staff",
                "done": False,
            }

        # 5. Fallback: use lightweight LLM for unrecognized queries
        return await self._llm_fallback(text)

    async def _llm_fallback(self, text: str) -> dict:
        """Use a lightweight LLM for queries that don't match keywords."""
        if self._llm_client is None:
            if not settings.openai_api_key:
                return {
                    "text": "잠시만요, 해당 문의는 직원에게 연결해 드릴게요.",
                    "action": "transfer_staff",
                    "done": False,
                }
            self._llm_client = AsyncOpenAI(api_key=settings.openai_api_key)

        self._messages.append({"role": "user", "content": text})

        try:
            response = await self._llm_client.chat.completions.create(
                model="gpt-4o-mini",  # Lightweight model for speed + cost
                messages=self._messages,
                tools=IVR_FUNCTION_DEFINITIONS,
                tool_choice="auto",
                temperature=0.5,
                max_tokens=200,
            )
        except Exception:
            logger.exception("ivr.llm_error")
            return {
                "text": "잠시만요, 해당 문의는 직원에게 연결해 드릴게요.",
                "action": "transfer_staff",
                "done": False,
            }

        message = response.choices[0].message

        # Handle function calls from LLM
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            self._messages.append(message.model_dump())

            if fn_name == "transfer_to_reservation":
                result_text = "네, 예약 도와드릴게요. 예약 담당으로 바로 연결해 드리겠습니다."
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"status": "transferring"}),
                })
                return {
                    "text": result_text,
                    "action": "transfer_reservation",
                    "done": False,
                }

            if fn_name == "transfer_to_staff":
                result_text = "네, 담당 직원에게 연결해 드릴게요. 잠시만 기다려 주세요."
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"status": "transferring"}),
                })
                return {
                    "text": result_text,
                    "action": "transfer_staff",
                    "done": False,
                }

            if fn_name == "provide_info":
                category = fn_args.get("category", "")
                # Look up from our menu items
                for item in self.config.menu_items:
                    if item.category == category:
                        self._messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(
                                {"info": item.response}, ensure_ascii=False
                            ),
                        })
                        return {
                            "text": item.response,
                            "action": "respond",
                            "done": False,
                        }
                # Category not found in our menu
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"info": "해당 정보가 등록되어 있지 않습니다."}),
                })
                return {
                    "text": "죄송해요, 해당 정보는 확인 후 안내드릴게요. "
                            "다른 궁금한 점 있으세요?",
                    "action": "respond",
                    "done": False,
                }

        # Regular text response
        assistant_text = message.content or ""
        self._messages.append({"role": "assistant", "content": assistant_text})

        done = any(
            phrase in assistant_text
            for phrase in ["감사합니다", "좋은 하루", "안녕히 가세요"]
        )

        return {
            "text": assistant_text,
            "action": "end" if done else "respond",
            "done": done,
        }

    @property
    def greeting(self) -> str:
        """The opening greeting message."""
        return self.config.greeting

    @property
    def menu_summary(self) -> str:
        """Human-readable summary of available menu items."""
        return ", ".join(item.label for item in self.config.menu_items)
