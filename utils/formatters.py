from __future__ import annotations

from datetime import datetime


def fmt_pct(value: float) -> str:
    return f"%{value:+.1f}"


def fmt_usd(value: float) -> str:
    return f"${value:,.0f}"


def fmt_date(value: datetime | None = None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    return (value or datetime.now()).strftime(fmt)
