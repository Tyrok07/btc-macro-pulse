from __future__ import annotations

import json
from pathlib import Path

import requests


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def save_state(path: Path, state: dict) -> None:
    try:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def send_telegram(token: str, chat_id: str, message: str) -> requests.Response | None:
    if not token or not chat_id:
        return None
    return requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
        timeout=10,
    )
