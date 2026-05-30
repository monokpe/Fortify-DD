import pytest

from app.clients.cognee import vendor_memory
from app.config import get_settings
from app.store import watchlist_store


@pytest.fixture(autouse=True)
def force_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()
    vendor_memory.clear()
    watchlist_store.clear()
    yield
    vendor_memory.clear()
    watchlist_store.clear()
    get_settings.cache_clear()
