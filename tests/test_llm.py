"""Tests for the LLM conversation handler."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.voice.llm import ReservationLLM
from src.voice.prompts.system import FUNCTION_DEFINITIONS, RESERVATION_SYSTEM_PROMPT


class TestReservationLLM:
    """Unit tests for LLM conversation handler."""

    def test_system_prompt_includes_restaurant_name(self):
        llm = ReservationLLM(restaurant_name="맛있는 한식당")
        assert llm.messages[0]["role"] == "system"
        assert "맛있는 한식당" in llm.messages[0]["content"]

    def test_default_restaurant_name(self):
        llm = ReservationLLM()
        assert "레스토랑" in llm.messages[0]["content"]

    @pytest.mark.asyncio
    async def test_process_message_text_response(self):
        """Should return text when LLM gives a direct response."""
        llm = ReservationLLM(restaurant_name="테스트식당")

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "안녕하세요, 테스트식당입니다. 예약 도와드릴까요?"

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(llm.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result = await llm.process_message("예약하고 싶어요")

            assert result["text"] == "안녕하세요, 테스트식당입니다. 예약 도와드릴까요?"
            assert result["function_call"] is None

    @pytest.mark.asyncio
    async def test_process_message_function_call(self):
        """Should return function_call when LLM wants to call a function."""
        llm = ReservationLLM()

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "check_availability"
        mock_tool_call.function.arguments = json.dumps({
            "date": "2025-02-03",
            "time": "18:00",
            "party_size": 4,
        })
        mock_tool_call.id = "call_123"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [{"id": "call_123"}],
        }

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(llm.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result = await llm.process_message("2월 3일 저녁 6시에 4명 예약 가능한가요?")

            assert result["function_call"] is not None
            assert result["function_call"]["name"] == "check_availability"
            assert result["function_call"]["arguments"]["party_size"] == 4
            assert result["text"] is None

    @pytest.mark.asyncio
    async def test_done_detection(self):
        """Should set done=True when farewell phrase is in response."""
        llm = ReservationLLM()

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "예약이 완료되었습니다. 감사합니다. 좋은 하루 보내세요!"

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(llm.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result = await llm.process_message("감사합니다")

            assert result["done"] is True

    @pytest.mark.asyncio
    async def test_provide_function_result(self):
        """Should feed function result back to LLM and get response."""
        llm = ReservationLLM()
        # Pre-fill message history to simulate a function call happened
        llm.messages.append({"role": "assistant", "tool_calls": [{"id": "call_123"}]})

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "네, 2월 3일 18시에 4명 자리가 있습니다. 예약하시겠어요?"

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(llm.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result_json = json.dumps({"available": True, "remaining_capacity": 16})
            result = await llm.provide_function_result("call_123", result_json)

            assert "자리가 있습니다" in result["text"]
            assert result["function_call"] is None

    def test_conversation_history_grows(self):
        """Message history should have system prompt initially."""
        llm = ReservationLLM()
        assert len(llm.messages) == 1
        assert llm.messages[0]["role"] == "system"


class TestFunctionDefinitions:
    """Verify function definitions are well-formed for OpenAI."""

    def test_all_functions_present(self):
        names = [f["function"]["name"] for f in FUNCTION_DEFINITIONS]
        assert "check_availability" in names
        assert "create_reservation" in names
        assert "cancel_reservation" in names
        assert "modify_reservation" in names
        assert "lookup_reservation" in names

    def test_check_availability_params(self):
        fn = next(f for f in FUNCTION_DEFINITIONS if f["function"]["name"] == "check_availability")
        params = fn["function"]["parameters"]
        assert "date" in params["properties"]
        assert "time" in params["properties"]
        assert "party_size" in params["properties"]
        assert set(params["required"]) == {"date", "time", "party_size"}

    def test_create_reservation_params(self):
        fn = next(f for f in FUNCTION_DEFINITIONS if f["function"]["name"] == "create_reservation")
        params = fn["function"]["parameters"]
        assert "customer_name" in params["properties"]
        assert "customer_phone" in params["properties"]
        required = set(params["required"])
        assert "customer_name" in required
        assert "customer_phone" in required


class TestSystemPrompt:
    """Verify system prompt contains required elements."""

    def test_contains_korean_honorifics_rule(self):
        assert "존댓말" in RESERVATION_SYSTEM_PROMPT

    def test_contains_reservation_info_fields(self):
        assert "날짜" in RESERVATION_SYSTEM_PROMPT
        assert "시간" in RESERVATION_SYSTEM_PROMPT
        assert "인원" in RESERVATION_SYSTEM_PROMPT
        assert "성함" in RESERVATION_SYSTEM_PROMPT

    def test_contains_restaurant_placeholder(self):
        assert "[식당 이름]" in RESERVATION_SYSTEM_PROMPT
