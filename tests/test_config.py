from rivalradar import config


def test_doubao_model_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("DOUBAO_MODEL", raising=False)
    assert config.doubao_model() == "ep-20260514111325-xjmj7"


def test_get_doubao_client_uses_base_url(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "dummy-key")
    monkeypatch.setenv("ARK_BASE_URL", "https://example.test/api/v3")
    client = config.get_doubao_client()
    assert str(client.base_url).rstrip("/") == "https://example.test/api/v3"
