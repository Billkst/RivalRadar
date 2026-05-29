from rivalradar.graph.build import build_research_graph
from rivalradar.storage.db import connect, init_db
import pytest


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


class _NoopProvider:
    name = "noop"

    def search(self, query, *, max_results=5):
        return []


def test_build_compiles_with_pipeline_nodes(conn):
    graph = build_research_graph(conn=conn, client=None, model="m",
                                 provider=_NoopProvider(), as_of="2026-05-26")
    names = set(graph.get_graph().nodes)
    # full-C 后含 decide 节点(Epic 2):collect→analyze→write→qc→decide→finalize
    assert {"collect", "analyze", "write", "qc", "decide", "finalize"} <= names
