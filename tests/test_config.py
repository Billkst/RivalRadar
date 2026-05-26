import pytest
from rivalradar import config


def test_doubao_model_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("DOUBAO_MODEL", raising=False)
    assert config.doubao_model() == "${DOUBAO_MODEL}"


def test_get_doubao_client_uses_base_url(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "dummy-key")
    monkeypatch.setenv("ARK_BASE_URL", "https://example.test/api/v3")
    client = config.get_doubao_client()
    assert str(client.base_url).rstrip("/") == "https://example.test/api/v3"


def test_get_doubao_client_raises_when_no_key(monkeypatch):
    """未设置 ARK_API_KEY → get_doubao_client 立即 ValueError,不静默返 None(KEY 纪律早报错)。"""
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ARK_API_KEY"):
        config.get_doubao_client()


def test_ark_api_key_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    assert config.ark_api_key() is None


def test_ark_api_key_returns_bool_true_when_set(monkeypatch):
    """KEY 纪律:只验 bool(),不断言 key 值本身。"""
    monkeypatch.setenv("ARK_API_KEY", "fake-key-for-test")
    assert bool(config.ark_api_key()) is True


def test_tavily_api_key_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert config.tavily_api_key() is None


def test_db_path_defaults(monkeypatch):
    monkeypatch.delenv("RIVALRADAR_DB", raising=False)
    assert config.db_path() == "rivalradar.db"


def test_db_path_from_env(monkeypatch):
    monkeypatch.setenv("RIVALRADAR_DB", "/tmp/test.db")
    assert config.db_path() == "/tmp/test.db"
