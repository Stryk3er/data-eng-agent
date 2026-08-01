"""Persisted incremental state.

One JSON file per source under state/. Committed to the repo (by the
scheduled/CI workflow) so the watermark survives across ephemeral CI runs,
not just on someone's laptop.
"""
import json
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / "state"


def load_state(source: str) -> dict:
    path = STATE_DIR / f"{source}.json"
    if not path.exists():
        return {"last_watermark": None}
    return json.loads(path.read_text())


def save_state(source: str, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{source}.json"
    path.write_text(json.dumps(state, indent=2, default=str) + "\n")
