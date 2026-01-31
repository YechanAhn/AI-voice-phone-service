"""LLM conversation handler for restaurant reservation dialogs."""

import json

import structlog
from openai import AsyncOpenAI

from src.config import settings
from src.voice.prompts.system import FUNCTION_DEFINITIONS, RESERVATION_SYSTEM_PROMPT

logger = structlog.get_logger()


class ReservationLLM:
    """GPT-4o based conversation handler with function calling for reservations.

    Manages multi-turn Korean restaurant reservation dialogs,
    including availability checks, bookings, modifications, and cancellations.
    """

    def __init__(self, restaurant_name: str = "레스토랑") -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
        self.restaurant_name = restaurant_name
        self.messages: list[dict] = [
            {
                "role": "system",
                "content": RESERVATION_SYSTEM_PROMPT.replace("[식당 이름]", restaurant_name),
            }
        ]

    async def process_message(self, user_text: str) -> dict:
        """Process a user message and return the assistant's response.

        Returns:
            dict with keys:
                - "text": response text to speak via TTS
                - "function_call": optional function call to execute
                - "done": whether the conversation should end
        """
        self.messages.append({"role": "user", "content": user_text})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=FUNCTION_DEFINITIONS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500,
        )

        message = response.choices[0].message

        # Handle function calls
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            self.messages.append(message.model_dump())

            return {
                "text": None,
                "function_call": {
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments),
                    "id": tool_call.id,
                },
                "done": False,
            }

        # Regular text response
        assistant_text = message.content or ""
        self.messages.append({"role": "assistant", "content": assistant_text})

        # Check if conversation should end
        done = any(
            phrase in assistant_text
            for phrase in ["감사합니다", "좋은 하루", "안녕히 가세요"]
        )

        return {"text": assistant_text, "function_call": None, "done": done}

    async def provide_function_result(self, tool_call_id: str, result: str) -> dict:
        """Feed the result of a function call back to the LLM.

        Args:
            tool_call_id: The ID of the tool call being responded to
            result: JSON string of the function result

        Returns:
            Same format as process_message
        """
        self.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": result}
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=FUNCTION_DEFINITIONS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500,
        )

        message = response.choices[0].message
        assistant_text = message.content or ""
        self.messages.append({"role": "assistant", "content": assistant_text})

        done = any(
            phrase in assistant_text
            for phrase in ["감사합니다", "좋은 하루", "안녕히 가세요"]
        )

        return {"text": assistant_text, "function_call": None, "done": done}
