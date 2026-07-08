from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import pandas as pd

from engine.metrics import MetricsEngine
from engine.portfolio import Portfolio
from engine.rebalance import Rebalancer
from engine.regimes import RegimeDetector, target_allocation_for_regime


@dataclass
class BacktestResult:
    data: pd.DataFrame
    trade_log: pd.DataFrame
    stats: Dict[str, Any]
    portfolio: Portfolio


class BacktestEngine:
    def __init__(
        self,
        initial_cash: float = 10000.0,
        commission: float = 0.0,
        slippage: float = 0.0,
        partial_rebalance: float = 1.0,
        tax_model: Callable[[Portfolio], None] | None = None,
    ) -> None:
        self.initial_cash = float(initial_cash)
        self.portfolio = Portfolio(initial_cash=self.initial_cash, commission=commission, slippage=slippage)
        self.rebalancer = Rebalancer(partial_rebalance=partial_rebalance)
        self.metrics = MetricsEngine(initial_cash=self.initial_cash)
        self.regime_detector = RegimeDetector()
        self.tax_model = tax_model

    def run(self, df: pd.DataFrame) -> BacktestResult:
        data = self.regime_detector.detect(df)
        self.portfolio.reset()
        previous_regime = None
        equity: List[float] = []
        trade_rows: List[Dict[str, Any]] = []

        for idx, row in data.iterrows():
            btc_price = float(row["Bitcoin"])
            gold_price = float(row["Altin"])
            regime = str(row["Regime"])
            changed = previous_regime is None or regime != previous_regime
            if changed:
                target = target_allocation_for_regime(regime)
                self.rebalancer.rebalance(self.portfolio, target, btc_price, gold_price, idx)
                if self.tax_model is not None:
                    self.tax_model(self.portfolio)
                port_after = self.portfolio.total_value(btc_price, gold_price)
                trade_rows.append({
                    "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                    "Geçiş": f"{previous_regime or 'Başlangıç'} → {regime}",
                    "Rejim": row["RegimeLabel"],
                    "Dağılım": f"BTC %{int(row['BtcPct'])} · Altın %{int(row['AltinPct'])}",
                    "Portföy": round(port_after, 0),
                    "Getiri": round((port_after / self.initial_cash - 1) * 100, 1),
                })
                previous_regime = regime
            equity.append(self.portfolio.snapshot(btc_price, gold_price))

        data = data.copy()
        data["Portfoy"] = equity
        data["BH_BTC"] = (self.initial_cash / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
        data["BH_Altin"] = (self.initial_cash / float(data["Altin"].iloc[0])) * data["Altin"]
        required = ["Bitcoin", "Altin", "Bakir", "Rasyo", "SMA10", "SMA50", "Portfoy", "BtcPct", "AltinPct", "BH_BTC", "BH_Altin"]
        data = data[[c for c in data.columns if c in set(required + ["Regime", "RegimeCode", "RegimeLabel", "RegimeDescription", "ShortBull", "MacroBull", "Renk10", "Renk50"])]]
        trade_log = pd.DataFrame(trade_rows)
        stats = self.metrics.evaluate(data, trade_log)
        return BacktestResult(data=data, trade_log=trade_log, stats=stats, portfolio=self.portfolio)
