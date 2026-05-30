import httpx

from app.config import Settings
from app.schemas import AlertPayload


class TriggerWareClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fire_alert(self, alert: AlertPayload) -> None:
        if self.settings.mock_mode or not self.settings.triggerware_webhook_url:
            return

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.settings.triggerware_webhook_url,
                json=alert.model_dump(mode="json"),
            )
            response.raise_for_status()
