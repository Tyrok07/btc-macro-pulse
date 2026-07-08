diff --git a/engine/backtest.py b/engine/backtest.py
index 6e26feea3dff452e63b3143f766c46ead7ad9e90..930824bc44fa4e2cb07539f71a7fd9bb9a0a09e8 100644
--- a/engine/backtest.py
+++ b/engine/backtest.py
@@ -1,140 +1,75 @@
+from __future__ import annotations
+
 from dataclasses import dataclass
+from typing import Any, Callable, Dict, List
+
 import pandas as pd
 
+from engine.metrics import MetricsEngine
 from engine.portfolio import Portfolio
-from engine.rebalance import Rebalancer, TargetAllocation
+from engine.rebalance import Rebalancer
+from engine.regimes import RegimeDetector, target_allocation_for_regime
 
 
 @dataclass
 class BacktestResult:
-    equity_curve: list
-    trades: list
+    data: pd.DataFrame
+    trade_log: pd.DataFrame
+    stats: Dict[str, Any]
     portfolio: Portfolio
 
 
 class BacktestEngine:
-
     def __init__(
         self,
-        initial_cash=10000,
-        btc_fee=0.001,
-        gold_fee=0.001,
-        slippage=0.0005
-    ):
-
-        self.portfolio = Portfolio(
-            initial_cash=initial_cash,
-            btc_fee=btc_fee,
-            gold_fee=gold_fee,
-            slippage=slippage
-        )
-
-        self.rebalancer = Rebalancer()
-
-    ###################################################################
-
-    def target_from_regime(self, regime):
-
-        if regime == "Güçlü Boğa":
-            return TargetAllocation(
-                btc=1.0,
-                gold=0.0
-            )
-
-        elif regime == "Boğa":
-            return TargetAllocation(
-                btc=0.75,
-                gold=0.25
-            )
-
-        elif regime == "Nötr":
-            return TargetAllocation(
-                btc=0.50,
-                gold=0.50
-            )
-
-        elif regime == "Ayı":
-
-            return TargetAllocation(
-                btc=0.25,
-                gold=0.75
-            )
-
-        else:
-
-            return TargetAllocation(
-                btc=0.0,
-                gold=1.0
-            )
-
-    ###################################################################
-
-    def run(self, df: pd.DataFrame):
-
+        initial_cash: float = 10000.0,
+        commission: float = 0.0,
+        slippage: float = 0.0,
+        partial_rebalance: float = 1.0,
+        tax_model: Callable[[Portfolio], None] | None = None,
+    ) -> None:
+        self.initial_cash = float(initial_cash)
+        self.portfolio = Portfolio(initial_cash=self.initial_cash, commission=commission, slippage=slippage)
+        self.rebalancer = Rebalancer(partial_rebalance=partial_rebalance)
+        self.metrics = MetricsEngine(initial_cash=self.initial_cash)
+        self.regime_detector = RegimeDetector()
+        self.tax_model = tax_model
+
+    def run(self, df: pd.DataFrame) -> BacktestResult:
+        data = self.regime_detector.detect(df)
+        self.portfolio.reset()
         previous_regime = None
-
-        for date, row in df.iterrows():
-
-            btc_price = row["BTC"]
-
-            gold_price = row["GOLD"]
-
-            regime = row["Regime"]
-
-            if previous_regime is None:
-
-                target = self.target_from_regime(regime)
-
-                self.rebalancer.rebalance(
-
-                    self.portfolio,
-
-                    target,
-
-                    btc_price,
-
-                    gold_price,
-
-                    date
-
-                )
-
+        equity: List[float] = []
+        trade_rows: List[Dict[str, Any]] = []
+
+        for idx, row in data.iterrows():
+            btc_price = float(row["Bitcoin"])
+            gold_price = float(row["Altin"])
+            regime = str(row["Regime"])
+            changed = previous_regime is None or regime != previous_regime
+            if changed:
+                target = target_allocation_for_regime(regime)
+                self.rebalancer.rebalance(self.portfolio, target, btc_price, gold_price, idx)
+                if self.tax_model is not None:
+                    self.tax_model(self.portfolio)
+                port_after = self.portfolio.total_value(btc_price, gold_price)
+                trade_rows.append({
+                    "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
+                    "Geçiş": f"{previous_regime or 'Başlangıç'} → {regime}",
+                    "Rejim": row["RegimeLabel"],
+                    "Dağılım": f"BTC %{int(row['BtcPct'])} · Altın %{int(row['AltinPct'])}",
+                    "Portföy": round(port_after, 0),
+                    "Getiri": round((port_after / self.initial_cash - 1) * 100, 1),
+                })
                 previous_regime = regime
-
-            elif regime != previous_regime:
-
-                target = self.target_from_regime(regime)
-
-                self.rebalancer.rebalance(
-
-                    self.portfolio,
-
-                    target,
-
-                    btc_price,
-
-                    gold_price,
-
-                    date
-
-                )
-
-                previous_regime = regime
-
-            self.portfolio.snapshot(
-
-                btc_price,
-
-                gold_price
-
-            )
-
-        return BacktestResult(
-
-            equity_curve=self.portfolio.equity_curve,
-
-            trades=self.portfolio.trades,
-
-            portfolio=self.portfolio
-
-        )
+            equity.append(self.portfolio.snapshot(btc_price, gold_price))
+
+        data = data.copy()
+        data["Portfoy"] = equity
+        data["BH_BTC"] = (self.initial_cash / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
+        data["BH_Altin"] = (self.initial_cash / float(data["Altin"].iloc[0])) * data["Altin"]
+        required = ["Bitcoin", "Altin", "Bakir", "Rasyo", "SMA10", "SMA50", "Portfoy", "BtcPct", "AltinPct", "BH_BTC", "BH_Altin"]
+        data = data[[c for c in data.columns if c in set(required + ["Regime", "RegimeCode", "RegimeLabel", "RegimeDescription", "ShortBull", "MacroBull", "Renk10", "Renk50"])]]
+        trade_log = pd.DataFrame(trade_rows)
+        stats = self.metrics.evaluate(data, trade_log)
+        return BacktestResult(data=data, trade_log=trade_log, stats=stats, portfolio=self.portfolio)
