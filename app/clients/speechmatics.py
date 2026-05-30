from urllib.parse import quote_plus

import httpx

from app.config import Settings
from app.schemas import AlertPayload


class SpeechmaticsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_alert_audio(self, alert: AlertPayload) -> str | None:
        if self.settings.mock_mode or not self.settings.speechmatics_api_key:
            return f"https://example.com/audio/{quote_plus(alert.vendor)}-risk-alert.mp3"

        headers = {
            "Authorization": f"Bearer {self.settings.speechmatics_api_key}",
            "Content-Type": "application/json",
        }
        script = (
            f"Vendor {alert.vendor} is now rated {alert.new_rating}. "
            f"{alert.summary} Recommended action: {alert.recommended_action}"
        )
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.settings.speechmatics_tts_endpoint,
                headers=headers,
                json={"text": script},
            )
            response.raise_for_status()
            payload = response.json()
        return payload.get("audio_url") or payload.get("url")
