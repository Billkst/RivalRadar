import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from rivalradar.storage.checkpointer import make_checkpointer


class _State(TypedDict):
    count: Annotated[int, operator.add]


def _inc(state: _State) -> dict:
    return {"count": 1}


def test_checkpointer_persists_state_across_invokes():
    saver = make_checkpointer(":memory:")
    builder = StateGraph(_State)
    builder.add_node("inc", _inc)
    builder.add_edge(START, "inc")
    builder.add_edge("inc", END)
    app = builder.compile(checkpointer=saver)

    cfg = {"configurable": {"thread_id": "t1"}}
    app.invoke({"count": 0}, cfg)
    app.invoke({"count": 0}, cfg)

    # 同 thread_id 二次 invoke,count 通过 checkpoint + reducer 累加证明状态被持久化
    assert app.get_state(cfg).values["count"] == 2
