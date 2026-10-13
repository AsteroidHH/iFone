"""Writes backend/tests/fixtures/mcp_catalog.json from the tools themselves. The console's built-in tool list is this file,
so it cannot drift; a backend test fails when the file is out of date.  python scripts/gen_catalog_fixture.py"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QUORUM_PERSISTENCE", "memory")
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "backend")]

from app.services.mcp_catalog import catalog  # noqa: E402

out = ROOT / "backend" / "tests" / "fixtures" / "mcp_catalog.json"
out.write_text(json.dumps({"tools": [{k: v for k, v in t.items() if k != "doc"} for t in catalog()]}, indent=2) + "\n", encoding="utf8")
print("wrote", out)
