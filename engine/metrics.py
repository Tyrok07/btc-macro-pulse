from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    cagr: float
    annual_volatility: float
    sharpe: float
    sortino: float
    mar: float
    max_drawdown: float
    win_rate: float
    average_trade: float
    exposure: float
    benchmark_comparison: Dict[str, float]


class MetricsEngine:
    def __init__(self, initial_cash: float = 10000.0, risk_free_rate: float = 0.0) -> None:
        self.initial_cash = float(initial_cash)
        self.risk_free_rate = float(risk_free_rate)

    def daily_returns(self, equity: Sequence[float]) -> pd.Series:
        return pd.Series(equity, dtype="float64").pct_change().dropna()

    def max_drawdown(self, equity: Sequence[float]) -> float:
        values = np.asarray(equity, dtype="float64")
        if values.size == 0:
            return 0.0
        running_max = np.maximum.accumulate(values)
        drawdown = values / running_max - 1.0
        return float(drawdown.min())

    def cagr(self, equity: Sequence[float]) -> float:
        values = np.asarray(equity, dtype="float64")
        if values.size < 2 or values[0] == 0:
            return 0.0
        years = values.size / 365.25
        return float((values[-1] / values[0]) ** (1 / years) - 1) if years > 0 else 0.0

    def evaluate(self, data: pd.DataFrame, trade_log: pd.DataFrame) -> Dict[str, Any]:
        equity = data["Portfoy"].astype(float)
        returns = self.daily_returns(equity)
        max_dd = self.max_drawdown(equity)
        cagr = self.cagr(equity)
        excess = returns - self.risk_free_rate / 365.0
        sharpe = 0.0 if excess.std() == 0 or np.isnan(excess.std()) else float(np.sqrt(365) * excess.mean() / excess.std())
        downside = returns[returns < 0]
        sortino = 0.0 if downside.std() == 0 or np.isnan(downside.std()) else float(np.sqrt(365) * returns.mean() / downside.std())
        rot_son = float(equity.iloc[-1])
        bh_btc_son = float(data["BH_BTC"].iloc[-1])
        bh_alt_son = float(data["BH_Altin"].iloc[-1])
        total_return = rot_son / self.initial_cash - 1.0
        trade_returns = trade_log["Getiri"].astype(float) if not trade_log.empty else pd.Series(dtype="float64")
        btc_days = int((data["BtcPct"] == 100).sum())
        gold_days = int((data["AltinPct"] == 100).sum())
        stats = {
            "islem_sayisi": int(len(trade_log)),
            "btc_gun": btc_days,
            "alt_gun": gold_days,
            "btc_gun_pct": btc_days / int(len(data)) * 100 if len(data) else 0.0,
            "alt_gun_pct": gold_days / int(len(data)) * 100 if len(data) else 0.0,
            "max_dd": round(max_dd * 100, 1),
            "toplam_gun": int(len(data)),
            "roi": total_return * 100,
            "cagr": cagr * 100,
            "sharpe": sharpe,
            "sortino": sortino,
            "mar": 0.0 if max_dd == 0 else cagr / abs(max_dd),
            "win_rate": 0.0 if trade_returns.empty else float((trade_returns > 0).mean() * 100),
            "average_trade": 0.0 if trade_returns.empty else float(trade_returns.mean()),
            "exposure": float(((data["BtcPct"] > 0) | (data["AltinPct"] > 0)).mean() * 100),
            "benchmark_comparison": {"btc": rot_son - bh_btc_son, "altin": rot_son - bh_alt_son},
            "rotation_advantage": rot_son - bh_btc_son,
            "rot_son": rot_son,
            "rot_kazanc": total_return * 100,
            "bh_btc_son": bh_btc_son,
            "bh_btc_k": (bh_btc_son / self.initial_cash - 1) * 100,
            "bh_alt_son": bh_alt_son,
            "bh_alt_k": (bh_alt_son / self.initial_cash - 1) * 100,
            "btc_degisim": float(data["Bitcoin"].pct_change().iloc[-1] * 100) if len(data) >= 2 else 0.0,
            "alt_degisim": float(data["Altin"].pct_change().iloc[-1] * 100) if len(data) >= 2 else 0.0,
        }
        return stats
