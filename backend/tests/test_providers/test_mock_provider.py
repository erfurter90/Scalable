from app.providers.mock_provider import MockProvider


def test_mock_provider_returns_ok_for_known_metrics():
    provider = MockProvider()

    for metric in provider.supported_metrics():
        result = provider.fetch(metric)
        assert result.status == "ok"
        assert result.value is not None
        assert result.source == "mock"


def test_mock_provider_unavailable_for_unknown_metric():
    provider = MockProvider()

    result = provider.fetch("does_not_exist")

    assert result.status == "unavailable"
    assert result.value is None


def test_mock_provider_fetch_price_known_coin():
    provider = MockProvider()

    result = provider.fetch_price("bitcoin", "eur")

    assert result.status == "ok"
    assert result.value == 60000.00


def test_mock_provider_fetch_price_unknown_coin():
    provider = MockProvider()

    result = provider.fetch_price("not-a-real-coin", "eur")

    assert result.status == "unavailable"
    assert result.value is None
