"""
Unit tests run the API logic on the in-memory view. Persistence and the FalkorDB gate have their own tests
(test_persistence.py, test_falkordb_gate.py) that talk to a real FalkorDB and fail loudly when it is not running.
"""
import os

os.environ.setdefault("QUORUM_PERSISTENCE", "memory")
