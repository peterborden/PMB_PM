import json

import httpx
import pytest

from app.ai import (
    AIRequestError,
    OpenRouterClient,
    build_chat_payload,
    parse_chat_response,
    _parse_json_from_text,
)


def test_build_chat_payload_uses_expected_shape() -> None:
    payload = build_chat_payload("openai/gpt-oss-120b", "2+2")
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["messages"] == [{"role": "user", "content": "2+2"}]
    assert payload["temperature"] == 0


def test_parse_chat_response_reads_text_content() -> None:
    payload = {
        "choices": [{"message": {"content": "4"}}],
    }
    assert parse_chat_response(payload) == "4"


def test_parse_chat_response_raises_for_missing_choices() -> None:
    with pytest.raises(AIRequestError):
        parse_chat_response({})


def test_openrouter_client_handles_http_and_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        data = json.loads(request.content.decode("utf-8"))
        assert data["messages"][0]["content"] == "2+2"
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "4"}}]},
        )

    client = OpenRouterClient(
        api_key="test-key",
        base_url="https://openrouter.example/api/v1",
        transport=httpx.MockTransport(handler),
    )
    assert client.ask("2+2") == "4"


def test_openrouter_client_surfaces_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    client = OpenRouterClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AIRequestError, match="timed out"):
        client.ask("2+2")


def test_parse_json_from_text_supports_code_fences() -> None:
    text = """```json
{"reply":"Done","updatedBoard":null}
```"""
    parsed = _parse_json_from_text(text)
    assert parsed["reply"] == "Done"


def test_run_board_assistant_parses_structured_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"reply":"Updated","updatedBoard":{"columns":[{"id":"col-backlog","title":"Backlog","cardIds":["card-1"]}],"cards":{"card-1":{"id":"card-1","title":"Task","details":"Details"}}}}'
                        }
                    }
                ]
            },
        )

    client = OpenRouterClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    result = client.run_board_assistant(
        board={
            "columns": [{"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1"]}],
            "cards": {"card-1": {"id": "card-1", "title": "Task", "details": "Details"}},
        },
        history=[],
        user_message="Rename backlog",
    )
    assert result["reply"] == "Updated"
    assert result["updatedBoard"]["columns"][0]["title"] == "Backlog"
