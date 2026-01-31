"""Tests for the Voice IVR (natural voice menu) system."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.voice.ivr import IVRConfig, MenuItem, VoiceIVR
from src.voice.prompts.ivr import DEFAULT_MENU_ITEMS, IVR_FUNCTION_DEFINITIONS, IVR_SYSTEM_PROMPT


class TestIVRConfig:
    """Tests for IVR configuration."""

    def test_default_config(self):
        config = IVRConfig()
        assert config.restaurant_name == "맛있는 식당"
        assert "맛있는 식당" in config.greeting
        assert config.enable_reservation_transfer is True
        assert len(config.menu_items) == len(DEFAULT_MENU_ITEMS)

    def test_custom_restaurant_name(self):
        config = IVRConfig(restaurant_name="서울 한식당")
        assert "서울 한식당" in config.greeting

    def test_custom_greeting(self):
        config = IVRConfig(greeting="반갑습니다. 무엇을 도와드릴까요?")
        assert config.greeting == "반갑습니다. 무엇을 도와드릴까요?"

    def test_custom_menu_items(self):
        items = [
            MenuItem(
                category="hours",
                label="영업시간",
                keywords=["영업시간", "몇시"],
                response="12시부터 10시까지예요.",
            )
        ]
        config = IVRConfig(menu_items=items)
        assert len(config.menu_items) == 1
        assert config.menu_items[0].response == "12시부터 10시까지예요."

    def test_default_menu_items_populated(self):
        config = IVRConfig()
        categories = [item.category for item in config.menu_items]
        assert "hours" in categories
        assert "location" in categories
        assert "parking" in categories
        assert "menu" in categories
        assert "private_room" in categories


class TestVoiceIVR:
    """Tests for the Voice IVR handler."""

    def test_greeting(self):
        ivr = VoiceIVR()
        assert "맛있는 식당" in ivr.greeting

    def test_menu_summary(self):
        ivr = VoiceIVR()
        summary = ivr.menu_summary
        assert "영업시간" in summary
        assert "위치" in summary

    # --- Keyword matching ---

    def test_match_keywords_found(self):
        ivr = VoiceIVR()
        assert ivr._match_keywords("예약하고 싶어요", ["예약", "부킹"]) is True

    def test_match_keywords_not_found(self):
        ivr = VoiceIVR()
        assert ivr._match_keywords("오늘 날씨 좋네요", ["예약", "부킹"]) is False

    def test_find_menu_match_hours(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("영업시간이 어떻게 되나요?")
        assert match is not None
        assert match.category == "hours"

    def test_find_menu_match_parking(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("주차장 있어요?")
        assert match is not None
        assert match.category == "parking"

    def test_find_menu_match_location(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("위치가 어디예요?")
        assert match is not None
        assert match.category == "location"

    def test_find_menu_match_menu(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("메뉴 뭐 있어요?")
        assert match is not None
        assert match.category == "menu"

    def test_find_menu_match_private_room(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("개인실 있나요?")
        assert match is not None
        assert match.category == "private_room"

    def test_find_menu_match_corkage(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("콜키지 가능한가요?")
        assert match is not None
        assert match.category == "corkage"

    def test_find_menu_match_kids(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("아이 의자 있어요?")
        assert match is not None
        assert match.category == "kids"

    def test_find_menu_match_pets(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("강아지 데려가도 되나요?")
        assert match is not None
        assert match.category == "pets"

    def test_find_menu_match_no_match(self):
        ivr = VoiceIVR()
        match = ivr._find_menu_match("오늘 날씨가 좋네요")
        assert match is None

    # --- Process utterance: keyword-based responses ---

    @pytest.mark.asyncio
    async def test_empty_text(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("")
        assert result["action"] == "respond"
        assert "다시 말씀해" in result["text"]

    @pytest.mark.asyncio
    async def test_farewell(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("감사합니다")
        assert result["action"] == "end"
        assert result["done"] is True
        assert "좋은 하루" in result["text"]

    @pytest.mark.asyncio
    async def test_farewell_bye(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("없어요 괜찮아요")
        assert result["done"] is True

    @pytest.mark.asyncio
    async def test_reservation_transfer(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("예약하고 싶은데요")
        assert result["action"] == "transfer_reservation"
        assert result["done"] is False
        assert "예약" in result["text"]

    @pytest.mark.asyncio
    async def test_reservation_cancel_transfer(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("예약 취소하려고요")
        assert result["action"] == "transfer_reservation"

    @pytest.mark.asyncio
    async def test_reservation_disabled(self):
        config = IVRConfig(enable_reservation_transfer=False)
        ivr = VoiceIVR(config=config)
        result = await ivr.process_utterance("예약하고 싶어요")
        assert result["action"] == "transfer_staff"

    @pytest.mark.asyncio
    async def test_staff_transfer(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("직원 연결해주세요")
        assert result["action"] == "transfer_staff"
        assert "직원" in result["text"]

    @pytest.mark.asyncio
    async def test_staff_transfer_manager(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("매니저 바꿔주세요")
        assert result["action"] == "transfer_staff"

    @pytest.mark.asyncio
    async def test_faq_hours(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("영업시간이 어떻게 되나요?")
        assert result["action"] == "respond"
        assert result["done"] is False
        assert "영업시간" in result["text"]

    @pytest.mark.asyncio
    async def test_faq_parking(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("주차 가능한가요?")
        assert result["action"] == "respond"
        assert "주차" in result["text"]

    @pytest.mark.asyncio
    async def test_faq_location(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("어떻게 찾아가나요?")
        assert result["action"] == "respond"
        assert "위치" in result["text"] or "강남" in result["text"]

    @pytest.mark.asyncio
    async def test_faq_menu(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("메뉴 추천해주세요")
        assert result["action"] == "respond"
        assert "메뉴" in result["text"] or "불고기" in result["text"]

    @pytest.mark.asyncio
    async def test_faq_pets(self):
        ivr = VoiceIVR()
        result = await ivr.process_utterance("반려동물 동반 가능한가요?")
        assert result["action"] == "respond"
        assert "반려동물" in result["text"] or "동반" in result["text"]

    # --- LLM fallback ---

    @pytest.mark.asyncio
    async def test_llm_fallback_text_response(self):
        """When keywords don't match, LLM should handle it."""
        ivr = VoiceIVR()

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "그 부분은 확인 후 안내드릴게요."

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ivr._llm_client = mock_client

        result = await ivr.process_utterance("오늘 특별한 이벤트 있나요?")
        assert result["action"] == "respond"
        assert "확인" in result["text"]

    @pytest.mark.asyncio
    async def test_llm_fallback_transfer_reservation(self):
        """LLM can decide to transfer to reservation."""
        ivr = VoiceIVR()

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "transfer_to_reservation"
        mock_tool_call.function.arguments = json.dumps({"reason": "reservation"})
        mock_tool_call.id = "call_ivr_1"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [{"id": "call_ivr_1"}],
        }

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ivr._llm_client = mock_client

        result = await ivr.process_utterance("자리 남아있나요?")
        assert result["action"] == "transfer_reservation"

    @pytest.mark.asyncio
    async def test_llm_fallback_transfer_staff(self):
        """LLM can decide to transfer to staff."""
        ivr = VoiceIVR()

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "transfer_to_staff"
        mock_tool_call.function.arguments = json.dumps({"reason": "custom request"})
        mock_tool_call.id = "call_ivr_2"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [{"id": "call_ivr_2"}],
        }

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ivr._llm_client = mock_client

        result = await ivr.process_utterance("케이터링 문의하고 싶어요")
        assert result["action"] == "transfer_staff"

    @pytest.mark.asyncio
    async def test_llm_fallback_provide_info(self):
        """LLM can call provide_info for a known category."""
        ivr = VoiceIVR()

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "provide_info"
        mock_tool_call.function.arguments = json.dumps({"category": "hours"})
        mock_tool_call.id = "call_ivr_3"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [{"id": "call_ivr_3"}],
        }

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ivr._llm_client = mock_client

        result = await ivr.process_utterance("언제 문 여나요?")
        assert result["action"] == "respond"
        assert "영업시간" in result["text"]

    @pytest.mark.asyncio
    async def test_llm_fallback_provide_info_unknown_category(self):
        """LLM calls provide_info with unknown category → graceful fallback."""
        ivr = VoiceIVR()

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "provide_info"
        mock_tool_call.function.arguments = json.dumps({"category": "wifi"})
        mock_tool_call.id = "call_ivr_4"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [{"id": "call_ivr_4"}],
        }

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ivr._llm_client = mock_client

        result = await ivr.process_utterance("와이파이 비밀번호 알려주세요")
        assert result["action"] == "respond"
        assert "확인" in result["text"]

    @pytest.mark.asyncio
    async def test_llm_fallback_error_handling(self):
        """When LLM fails, should transfer to staff."""
        ivr = VoiceIVR()

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )
        ivr._llm_client = mock_client

        result = await ivr.process_utterance("특이한 질문이에요")
        assert result["action"] == "transfer_staff"
        assert "직원" in result["text"]

    @pytest.mark.asyncio
    async def test_llm_fallback_no_api_key(self):
        """Without API key, should transfer to staff."""
        ivr = VoiceIVR()
        ivr._llm_client = None

        with patch("src.voice.ivr.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            result = await ivr.process_utterance("특이한 질문이에요")
            assert result["action"] == "transfer_staff"

    @pytest.mark.asyncio
    async def test_llm_fallback_done_detection(self):
        """LLM response with farewell should set done=True."""
        ivr = VoiceIVR()

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "네, 감사합니다. 좋은 하루 보내세요!"

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        ivr._llm_client = mock_client

        result = await ivr.process_utterance("그럼 감사합니다")
        assert result["done"] is True
        assert result["action"] == "end"


class TestIVRPrompts:
    """Tests for IVR prompt definitions."""

    def test_system_prompt_has_placeholder(self):
        assert "[식당 이름]" in IVR_SYSTEM_PROMPT
        assert "[메뉴 항목]" in IVR_SYSTEM_PROMPT

    def test_system_prompt_mentions_key_concepts(self):
        assert "존댓말" in IVR_SYSTEM_PROMPT
        assert "예약" in IVR_SYSTEM_PROMPT
        assert "직원" in IVR_SYSTEM_PROMPT

    def test_function_definitions_present(self):
        names = [f["function"]["name"] for f in IVR_FUNCTION_DEFINITIONS]
        assert "provide_info" in names
        assert "transfer_to_reservation" in names
        assert "transfer_to_staff" in names

    def test_provide_info_has_categories(self):
        fn = next(
            f for f in IVR_FUNCTION_DEFINITIONS
            if f["function"]["name"] == "provide_info"
        )
        categories = fn["function"]["parameters"]["properties"]["category"]["enum"]
        assert "hours" in categories
        assert "location" in categories
        assert "parking" in categories
        assert "menu" in categories


class TestDefaultMenuItems:
    """Tests for default menu item templates."""

    def test_all_categories_present(self):
        assert "hours" in DEFAULT_MENU_ITEMS
        assert "location" in DEFAULT_MENU_ITEMS
        assert "parking" in DEFAULT_MENU_ITEMS
        assert "menu" in DEFAULT_MENU_ITEMS
        assert "private_room" in DEFAULT_MENU_ITEMS
        assert "corkage" in DEFAULT_MENU_ITEMS
        assert "kids" in DEFAULT_MENU_ITEMS
        assert "pets" in DEFAULT_MENU_ITEMS

    def test_each_item_has_required_fields(self):
        for category, item in DEFAULT_MENU_ITEMS.items():
            assert "label" in item, f"{category} missing label"
            assert "keywords" in item, f"{category} missing keywords"
            assert "response" in item, f"{category} missing response"
            assert len(item["keywords"]) > 0, f"{category} has no keywords"
            assert len(item["response"]) > 0, f"{category} has empty response"

    def test_keywords_are_korean(self):
        for category, item in DEFAULT_MENU_ITEMS.items():
            for kw in item["keywords"]:
                assert len(kw) > 0, f"{category} has empty keyword"


class TestMenuItem:
    """Tests for MenuItem dataclass."""

    def test_create_menu_item(self):
        item = MenuItem(
            category="test",
            label="테스트",
            keywords=["테스트", "시험"],
            response="테스트 응답입니다.",
        )
        assert item.category == "test"
        assert item.label == "테스트"
        assert len(item.keywords) == 2
        assert item.response == "테스트 응답입니다."
