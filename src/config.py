from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # LiveKit
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # Telephony (Telnyx)
    telnyx_api_key: str = ""
    telnyx_sip_trunk_id: str = ""
    telnyx_phone_number: str = ""

    # STT - Return Zero
    rtzr_client_id: str = ""
    rtzr_client_secret: str = ""

    # STT - CLOVA Speech
    clova_speech_secret_key: str = ""
    clova_speech_invoke_url: str = ""

    # TTS - CLOVA Voice
    clova_voice_client_id: str = ""
    clova_voice_client_secret: str = ""
    clova_voice_speaker: str = "nara"

    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"

    # Restaurant
    restaurant_name: str = "맛있는 식당"
    restaurant_id: int = 1

    # Service Mode: "full" (AI reservation) or "ivr" (natural voice menu)
    service_mode: str = "full"

    # IVR Settings (used when service_mode="ivr")
    ivr_enable_reservation_transfer: bool = True
    ivr_staff_transfer_number: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/reservations"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Naver Booking
    naver_booking_client_id: str = ""
    naver_booking_client_secret: str = ""
    naver_business_id: str = ""

    # CatchTable
    catchtable_api_key: str = ""
    catchtable_restaurant_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
