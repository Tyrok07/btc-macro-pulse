from __future__ import annotations

import pandas as pd


class IndicatorEngine:
    @staticmethod
    def sma(series: pd.Series, length: int) -> pd.Series:
        return series.rolling(length).mean()

    @staticmethod
    def ema(series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length).mean()

    @staticmethod
    def ratio(a: pd.Series, b: pd.Series) -> pd.Series:
        return a / b

    @staticmethod
    def pct(series: pd.Series) -> pd.Series:
        return series.pct_change()

    @staticmethod
    def returns(series: pd.Series) -> pd.Series:
        return series.pct_change().fillna(0)


class IndicatorBuilder:
    REQUIRED_COLUMNS = ["Altin", "Bakir", "Bitcoin"]

    @classmethod
    def add_liquidity_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        cls.validate_columns(d)
        d["Rasyo"] = IndicatorEngine.ratio(d["Altin"], d["Bakir"] * d["Bitcoin"])
        d["SMA10"] = IndicatorEngine.sma(d["Rasyo"], 10)
        d["SMA50"] = IndicatorEngine.sma(d["Rasyo"], 50)
        return d

    @classmethod
    def validate_columns(cls, df: pd.DataFrame) -> None:
        missing = [column for column in cls.REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(f"Eksik veri sütunları: {', '.join(missing)}")
