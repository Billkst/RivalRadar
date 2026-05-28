"""Cancel API + mark_run_cancelled CAS tests(plan v3.2 §10 D5 Epic 7.5b)。

覆盖 4 个 cancel 路径:
  1. unknown run → idempotent no-crash
  2. already done run → CAS guard,db 不被覆盖
  3. running run + active task → task.cancel() + DB 切 cancelled
  4. repo.mark_run_cancelled CAS 直接单元测试(running → cancelled / done → no-op)

依赖:_ACTIVE_RUN_TASKS module-level dict 用 FakeTask 模拟 active graph task
(asyncio.Task 真创建需要 event loop,FakeTask 简单 mock done()/cancel() 即可
验证 endpoint 调用逻辑)。
"""
import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.api.sse import _ACTIVE_RUN_TASKS
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "cancel.db")


@pytest.fixture()
def client(db_path):
    return TestClient(create_app(db_path=db_path))


@pytest.fixture(autouse=True)
def _clear_active_tasks():
    """每个 test 前后清 _ACTIVE_RUN_TASKS 防测试间污染(module-level state)。"""
    _ACTIVE_RUN_TASKS.clear()
    yield
    _ACTIVE_RUN_TASKS.clear()


def _seed_run(db_path: str, run_id: str, status: str = "running") -> None:
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, run_id, ["Notion"], ["pricing"])
    if status != "running":
        repo.update_run_status(c, run_id, status)
    c.close()


class FakeTask:
    """Mock asyncio.Task 让 cancel API 不需要真 event loop。"""
    def __init__(self) -> None:
        self.cancel_called = False
        self._done = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancel_called = True
        self._done = True


def test_cancel_unknown_run_idempotent(client):
    """未知 run_id cancel 不 crash —— cancelled=False / db_cancelled=False。

    场景:user 在 stale UI 上点 cancel,run_id 不在 _ACTIVE_RUN_TASKS 且 DB
    无记录。endpoint 应该 graceful 返响应,不 404 不 500。
    """
    r = client.post("/run/no_such_run/cancel")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "no_such_run"
    assert body["cancelled"] is False
    assert body["db_cancelled"] is False


def test_cancel_already_done_run_idempotent(db_path, client):
    """已 done 的 run cancel → CAS guard 防覆盖,db 状态保 done。

    场景:user cancel 时 run 刚好 finalize 完(timing race)。CAS WHERE status=
    'running' 失败 → db_cancelled=False,db status 保持 done(不被错误覆盖到
    cancelled)。
    """
    _seed_run(db_path, "r_done", status="done")
    r = client.post("/run/r_done/cancel")
    assert r.status_code == 200
    body = r.json()
    assert body["cancelled"] is False  # 无 active task
    assert body["db_cancelled"] is False  # CAS guard prevented overwrite

    c = connect(db_path)
    run = repo.get_run(c, "r_done")
    assert run["status"] == "done"  # 仍 done
    c.close()


def test_cancel_running_run_marks_cancelled_and_calls_task_cancel(db_path, client):
    """running run + active task → task.cancel() + DB CAS 成功切 cancelled。"""
    _seed_run(db_path, "r_run", status="running")
    fake_task = FakeTask()
    _ACTIVE_RUN_TASKS["r_run"] = fake_task

    r = client.post("/run/r_run/cancel")
    assert r.status_code == 200
    body = r.json()
    assert body["cancelled"] is True  # task.cancel() 被调
    assert body["db_cancelled"] is True  # CAS 成功
    assert fake_task.cancel_called is True

    c = connect(db_path)
    run = repo.get_run(c, "r_run")
    assert run["status"] == "cancelled"
    c.close()


def test_mark_run_cancelled_CAS_only_when_running(db_path):
    """repo.mark_run_cancelled CAS:仅 status='running' 时切 cancelled。"""
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r_running", ["Notion"], ["pricing"])
    repo.create_run(c, "r_done", ["Coda"], ["pricing"])
    repo.update_run_status(c, "r_done", "done")

    # running → cancelled,返 True
    assert repo.mark_run_cancelled(c, "r_running") is True
    assert repo.get_run(c, "r_running")["status"] == "cancelled"

    # done → CAS guard,返 False
    assert repo.mark_run_cancelled(c, "r_done") is False
    assert repo.get_run(c, "r_done")["status"] == "done"  # 仍 done

    # 二次 cancel 已 cancelled run → False(idempotent)
    assert repo.mark_run_cancelled(c, "r_running") is False
    c.close()


def test_mark_run_finalized_CAS_guards_cancel_race(db_path):
    """repo.mark_run_finalized CAS:cancel-finalize race 不会覆盖 cancelled 状态。

    场景(post-ship review fix):cancel POST 先 CAS 把 status 设 'cancelled',
    紧跟着 finalize_node sync 跑完想写 'done' — 必须被 CAS 拒绝(expected='running')。
    """
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r_running", ["Notion"], ["pricing"])
    repo.create_run(c, "r_cancelled", ["Coda"], ["pricing"])

    # 模拟 cancel 已发生:CAS 把 r_cancelled 切 cancelled
    assert repo.mark_run_cancelled(c, "r_cancelled") is True

    # 模拟 finalize 紧跟着想覆盖 'cancelled' → 'done':必须 CAS 拒绝
    assert repo.mark_run_finalized(c, "r_cancelled", "done") is False
    assert repo.get_run(c, "r_cancelled")["status"] == "cancelled"  # 保留 cancelled

    # 正常路径:running run finalize 成功
    assert repo.mark_run_finalized(c, "r_running", "done") is True
    assert repo.get_run(c, "r_running")["status"] == "done"

    # 已 done run 再 finalize → CAS 拒绝(idempotent)
    assert repo.mark_run_finalized(c, "r_running", "degraded") is False
    assert repo.get_run(c, "r_running")["status"] == "done"  # 仍 done
    c.close()
