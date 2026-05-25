from rivalradar import config


def test_default_doubao_model():
    assert config.DEFAULT_DOUBAO_MODEL == "ep-20260514111325-xjmj7"


def test_get_doubao_client_uses_base_url(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "dummy-key")
    monkeypatch.setenv("ARK_BASE_URL", "https://example.test/api/v3")
    client = config.get_doubao_client()
    assert str(client.base_url).rstrip("/") == "https://example.test/api/v3"
