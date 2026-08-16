from decimal import Decimal

from app.core.config import get_settings
from app.models.financial_snapshot import EntryType
from app.schemas.financial import FinancialEntryCreate
from app.services import chat_service, financial_service


def test_answer_question_without_api_key_degrades_gracefully(db_session, test_user, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()

    result = chat_service.answer_question(db_session, test_user.id, "Wie hoch ist mein Cash?")

    assert result["ai_available"] is False
    assert result["reply"] is None
    assert result["error"] is None

    get_settings.cache_clear()


def test_answer_question_with_key_calls_llm_and_uses_computed_data(db_session, test_user, today, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")
    get_settings.cache_clear()

    financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.asset,
            category="holding",
            subcategory="cash",
            label="checking",
            amount=Decimal("1234.00"),
            snapshot_date=today,
        ),
    )

    captured = {}

    class FakeLlmClient:
        is_configured = True

        def complete(self, system_prompt, user_message):
            captured["system_prompt"] = system_prompt
            captured["user_message"] = user_message
            return "You have 1234.00 EUR in cash."

    monkeypatch.setattr(chat_service, "get_llm_client", lambda: FakeLlmClient())

    result = chat_service.answer_question(db_session, test_user.id, "Wie viel Cash habe ich?")

    assert result["ai_available"] is True
    assert result["reply"] == "You have 1234.00 EUR in cash."
    assert result["data_used"]["available"] is True
    assert result["data_used"]["cash_total"] == 1234.00
    assert "1234" in captured["user_message"]

    get_settings.cache_clear()


def test_answer_question_llm_error_does_not_crash(db_session, test_user, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")
    get_settings.cache_clear()

    class FailingLlmClient:
        is_configured = True

        def complete(self, system_prompt, user_message):
            raise RuntimeError("upstream API unavailable")

    monkeypatch.setattr(chat_service, "get_llm_client", lambda: FailingLlmClient())

    result = chat_service.answer_question(db_session, test_user.id, "Wie hoch ist mein Cash?")

    assert result["ai_available"] is True
    assert result["reply"] is None
    assert "upstream API unavailable" in result["error"]

    get_settings.cache_clear()


def test_unrecognized_question_reports_unsupported(db_session, test_user, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")
    get_settings.cache_clear()

    class FakeLlmClient:
        is_configured = True

        def complete(self, system_prompt, user_message):
            return "I can't help with that yet."

    monkeypatch.setattr(chat_service, "get_llm_client", lambda: FakeLlmClient())

    result = chat_service.answer_question(db_session, test_user.id, "What's the weather like?")

    assert result["data_used"]["available"] is False

    get_settings.cache_clear()
