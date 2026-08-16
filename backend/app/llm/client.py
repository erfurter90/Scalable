"""Thin wrapper around the Anthropic SDK. The one and only place in the app that talks to
an LLM. If ANTHROPIC_API_KEY isn't set, `is_configured` is False and `complete()` is never
called — callers must check `is_configured` first (see chat_service.answer_question) so the
app degrades to a clear "not configured" state instead of crashing.
"""

from anthropic import Anthropic

from app.core.config import get_settings


class LlmClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.anthropic_model
        self._client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def complete(self, system_prompt: str, user_message: str) -> str:
        if self._client is None:
            raise RuntimeError("LlmClient.complete() called while not configured — check is_configured first")

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


def get_llm_client() -> LlmClient:
    """Not cached, deliberately: constructing it is cheap, and re-reading settings on every
    call keeps behavior correct if ANTHROPIC_API_KEY changes between requests (e.g. in tests,
    or after editing .env without a full app restart in some deployments)."""
    return LlmClient()
