from __future__ import annotations

import pandas as pd

from data.indicators import IndicatorBuilder


REQUIRED_MARKET_COLUMNS = ["Altin", "Bakir", "Bitcoin"]


def preprocess(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return raw.copy()
    data = raw.copy()
    IndicatorBuilder.validate_columns(data)
    data = data[REQUIRED_MARKET_COLUMNS].ffill().bfill().dropna()
    return data


def validate_market_data(raw: pd.DataFrame, minimum_rows: int = 60) -> str | None:
    if raw.empty or len(raw) < minimum_rows:
        return "Veri yeterli büyüklükte değil."
    for column in REQUIRED_MARKET_COLUMNS:
        if column not in raw.columns:
            return f"'{column}' verisi çekilemedi. Lütfen sayfayı yenileyin."
        if raw[column].isna().all():
            return f"'{column}' verisi tamamen boş. Lütfen sayfayı yenileyin."
    return None
