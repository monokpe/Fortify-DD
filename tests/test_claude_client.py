import pytest

from app.clients.claude import ClaudeSynthesizer
from app.config import Settings


def test_extract_json_returns_embedded_json_object() -> None:
    synthesizer = ClaudeSynthesizer(Settings())

    extracted = synthesizer._extract_json('Here is the brief:\n{"company": "Acme"}\nDone.')

    assert extracted == '{"company": "Acme"}'


def test_extract_json_raises_when_response_contains_no_json() -> None:
    synthesizer = ClaudeSynthesizer(Settings())

    with pytest.raises(ValueError, match="did not contain a JSON object"):
        synthesizer._extract_json("I cannot produce the requested JSON.")


@pytest.mark.parametrize(
    "content",
    [
        'Prefix only {"company": "Acme"',
        'Closing before opening } then {"company": "Acme"',
    ],
)
def test_extract_json_raises_for_malformed_partial_json(content: str) -> None:
    synthesizer = ClaudeSynthesizer(Settings())

    with pytest.raises(ValueError, match="did not contain a JSON object"):
        synthesizer._extract_json(content)
