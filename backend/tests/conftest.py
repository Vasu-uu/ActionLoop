import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["LLM_PROVIDER"] = "demo"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["SAMPLES_DIR"] = str(ROOT / "samples")
os.environ["FRONTEND_DIST"] = str(ROOT / "nonexistent-dist")

import pytest  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import config, db
    from app.services import llm

    config.reset_settings()
    db.reset_engine()
    llm.reset_provider()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
    db.reset_engine()


def sample_text(sample_id: str) -> str:
    import json

    idx = json.loads((ROOT / "samples" / "index.json").read_text(encoding="utf-8"))
    f = next(s["file"] for s in idx if s["id"] == sample_id)
    return (ROOT / "samples" / f).read_text(encoding="utf-8")


SAMPLE_IDS = ["startup-standup", "club-planning", "project-retro"]
