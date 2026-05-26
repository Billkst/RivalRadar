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
