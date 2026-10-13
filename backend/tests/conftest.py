"""
Unit tests run the API logic on the in-memory view. Persistence and the FalkorDB gate have their own tests
(test_persistence.py, test_falkordb_gate.py) that talk to a real FalkorDB and fail loudly when it is not running.
"""
import os

os.environ.setdefault("QUORUM_PERSISTENCE", "memory")
# Limits have their own tests; the rest of the suite should not trip them.
os.environ.setdefault("QUORUM_RATE_LIMIT_HTTP_PER_MIN", "0")
os.environ.setdefault("QUORUM_RATE_LIMIT_TOOLS_PER_MIN", "0")

import pytest


@pytest.fixture(autouse=True)
def fixture_acme():
    """Older tests expect the demo fixtures in tenant acme. Product code never loads them; tests ask for them here."""
    from app.graph import queries
    from app.services.fixtures import seed_store

    queries.forget_stores()
    seed_store(queries.get_graph_store("acme"))
    yield
