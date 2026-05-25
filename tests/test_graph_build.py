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


def test_build_compiles_with_five_nodes(conn):
    graph = build_research_graph(conn=conn, client=None, model="m",
                                 provider=_NoopProvider(), as_of="2026-05-26")
    names = set(graph.get_graph().nodes)
    assert {"collect", "analyze", "write", "qc", "finalize"} <= names
