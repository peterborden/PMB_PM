import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from .models import BoardAssistantOutput

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-oss-120b"
OPENROUTER_DEFAULT_TIMEOUT_SECONDS = 20.0


class AIConfigError(Exception):
    pass


class AIRequestError(Exception):
    pass


def build_chat_payload(model: str, user_prompt: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0,
    }


def parse_chat_response(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIRequestError("OpenRouter response missing choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise AIRequestError("OpenRouter choice payload invalid")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AIRequestError("OpenRouter response missing message")

    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
        if not text:
            raise AIRequestError("OpenRouter response content empty")
        return text

    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
        if chunks:
            return "\n".join(chunks)

    raise AIRequestError("OpenRouter response did not include text content")


def _parse_json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIRequestError("AI response was not valid JSON")

    snippet = stripped[start : end + 1]
    try:
        parsed = json.loads(snippet)
    except ValueError as error:
        raise AIRequestError("AI response was not valid JSON") from error

    if not isinstance(parsed, dict):
        raise AIRequestError("AI response JSON was not an object")
    return parsed


@dataclass
class OpenRouterClient:
    api_key: str
    model: str = OPENROUTER_DEFAULT_MODEL
    base_url: str = OPENROUTER_DEFAULT_BASE_URL
    timeout_seconds: float = OPENROUTER_DEFAULT_TIMEOUT_SECONDS
    app_name: str = "Project Management MVP"
    http_referer: str = "http://localhost"
    transport: httpx.BaseTransport | None = None

    @classmethod
    def from_env(cls) -> "OpenRouterClient":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise AIConfigError("OPENROUTER_API_KEY is not configured")

        timeout_value = os.getenv("OPENROUTER_TIMEOUT_SECONDS")
        timeout_seconds = OPENROUTER_DEFAULT_TIMEOUT_SECONDS
        if timeout_value:
            try:
                timeout_seconds = float(timeout_value)
            except ValueError as error:
                raise AIConfigError("OPENROUTER_TIMEOUT_SECONDS must be numeric") from error

        model = os.getenv("OPENROUTER_MODEL", OPENROUTER_DEFAULT_MODEL)
        base_url = os.getenv("OPENROUTER_BASE_URL", OPENROUTER_DEFAULT_BASE_URL)
        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    def run_diagnostic(self) -> dict[str, str]:
        prompt = "2+2"
        answer = self.ask(prompt)
        return {"model": self.model, "prompt": prompt, "answer": answer}

    def run_board_assistant(
        self,
        board: dict[str, Any],
        history: list[dict[str, str]],
        user_message: str,
    ) -> dict[str, Any]:
        system_prompt = (
            "You are a kanban assistant. "
            "Return ONLY valid JSON with shape: "
            '{"reply":"string","updatedBoard":<board object or null>}. '
            "A board has columns (each with id, title, cardIds) and a cards map. "
            "Each card has id, title, details, an optional labels array of short "
            'text tags, and an optional dueDate as an ISO date string "YYYY-MM-DD" '
            "(or null). Preserve any existing labels and dueDate unless the user "
            "asks to change them. "
            "If no board change is needed, set updatedBoard to null."
        )
        board_context = json.dumps(board, ensure_ascii=True, separators=(",", ":"))
        prompt = (
            "Current board JSON:\n"
            f"{board_context}\n\n"
            "User message:\n"
            f"{user_message}\n\n"
            "Return the JSON response now."
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        # Ask for a JSON object response; _parse_json_from_text still tolerates
        # fenced or wrapped output if the model ignores the hint.
        raw_text = self._ask_messages(
            messages, response_format={"type": "json_object"}
        )
        payload = _parse_json_from_text(raw_text)
        parsed = BoardAssistantOutput.model_validate(payload)
        return parsed.model_dump()

    def ask(self, prompt: str) -> str:
        payload = build_chat_payload(self.model, prompt)
        return self._post_chat(payload)

    def _ask_messages(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        return self._post_chat(payload)

    def _post_chat(self, payload: dict[str, Any]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
            "HTTP-Referer": self.http_referer,
        }

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as error:
            raise AIRequestError("OpenRouter request timed out") from error
        except httpx.RequestError as error:
            raise AIRequestError(f"OpenRouter request failed: {error}") from error

        if response.status_code >= 400:
            body = response.text.strip()
            if len(body) > 300:
                body = f"{body[:300]}..."
            raise AIRequestError(
                f"OpenRouter error {response.status_code}: {body or 'no body'}"
            )

        try:
            response_payload = response.json()
        except ValueError as error:
            raise AIRequestError("OpenRouter response was not valid JSON") from error

        return parse_chat_response(response_payload)
