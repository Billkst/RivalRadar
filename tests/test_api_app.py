def test_api_module_imports():
    import rivalradar.api  # noqa: F401


import pytest
from pydantic import ValidationError


def test_run_request_validates_non_empty():
    from rivalradar.api.schemas import RunRequest
    req = RunRequest(competitors=["Notion"], dimensions=["pricing"])
    assert req.competitors == ["Notion"]
    with pytest.raises(ValidationError):
        RunRequest(competitors=[], dimensions=["pricing"])  # 空竞品列表非法
    with pytest.raises(ValidationError):
        RunRequest(competitors=["X"], dimensions=[])        # 空维度非法


def test_annotation_create_requires_note():
    from rivalradar.api.schemas import AnnotationCreate
    a = AnnotationCreate(run_id="r1", evidence_id="ev1",
                         conclusion_path=None, note="可疑")
    assert a.note == "可疑"
    with pytest.raises(ValidationError):
        AnnotationCreate(run_id="r1", evidence_id=None,
                         conclusion_path=None, note="")  # 空 note 非法


from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    from rivalradar.api.app import create_app
    db = tmp_path / "test.db"
    app = create_app(db_path=str(db))
    return TestClient(app)


def test_healthcheck_returns_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_healthcheck_does_not_leak_api_key(client):
    """🔑 KEY 纪律:健康检查只返 bool,绝不返 key 值。"""
    r = client.get("/healthz")
    body = r.text
    for s in ("sk-", "ARK_API_KEY", "secret", "Bearer "):
        assert s not in body


def test_cors_headers_present(client):
    r = client.options("/healthz",
                       headers={"origin": "http://localhost:3000",
                                "access-control-request-method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "*"


def test_404_returns_json_error(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert "detail" in r.json()
