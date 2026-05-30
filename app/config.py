from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    mock_mode: bool = True

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    aiml_api_key: str | None = None
    aiml_base_url: str = "https://api.aimlapi.com/v1"
    aiml_triage_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

    bright_data_api_key: str | None = None
    bright_data_request_endpoint: str = "https://api.brightdata.com/request"
    bright_data_serp_zone: str | None = None
    bright_data_web_unlocker_zone: str | None = None
    bright_data_mcp_token: str | None = None

    triggerware_api_key: str | None = None
    triggerware_base_url: str = "https://api.triggerware.com"
    triggerware_trigger_name: str = "vendor_risk_changes"
    triggerware_schedule_seconds: int = 86400
    triggerware_webhook_url: str | None = None

    speechmatics_api_key: str | None = None
    speechmatics_tts_endpoint: str = "https://asr.api.speechmatics.com/v2/tts"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
