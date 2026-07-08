from __future__ import annotations

import pandas as pd

from engine.rebalance import TargetAllocation


def rejim_tespit(r, s10, s50):
    if r < s10 and r < s50:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢🟢 GÜÇLÜ BOĞA", "Her iki sinyal BTC lehine · En güçlü alım bölgesi")
    if r < s50:
        return ("Boğa + Düzeltme", 50, 50, "weak-on", "🟡🟢 BOĞA + Kısa Düzeltme", "Büyük trend yukarı · Kısa vadede hafif baskı")
    if r < s10:
        return ("Ayı + Toparlanma", 0, 100, "weak-off", "🟠🔴 AYI + Kısa Toparlanma", "Büyük trend aşağı · Kısa vadede geçici rahatlama")
    return ("Güçlü Ayı", 0, 100, "strong-off", "🔴🔴 GÜÇLÜ AYI", "Her iki sinyal BTC aleyhine · Altın koruma modu")


def target_allocation_for_regime(regime: str) -> TargetAllocation:
    if regime == "Güçlü Boğa":
        return TargetAllocation(btc=1.0, gold=0.0)
    if regime == "Boğa + Düzeltme":
        return TargetAllocation(btc=0.5, gold=0.5)
    return TargetAllocation(btc=0.0, gold=1.0)


class RegimeDetector:
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
        d["SMA10"] = d["Rasyo"].rolling(10).mean()
        d["SMA50"] = d["Rasyo"].rolling(50).mean()
        d = d.dropna().copy()
        details = d.apply(lambda row: rejim_tespit(row["Rasyo"], row["SMA10"], row["SMA50"]), axis=1)
        d["Regime"] = details.map(lambda x: x[0])
        d["BtcPct"] = details.map(lambda x: x[1])
        d["AltinPct"] = details.map(lambda x: x[2])
        d["RegimeCode"] = details.map(lambda x: x[3])
        d["RegimeLabel"] = details.map(lambda x: x[4])
        d["RegimeDescription"] = details.map(lambda x: x[5])
        d["ShortBull"] = d["Rasyo"] < d["SMA10"]
        d["MacroBull"] = d["Rasyo"] < d["SMA50"]
        d["Renk10"] = d["ShortBull"].map({True: "#4ADE80", False: "#F87171"})
        d["Renk50"] = d["MacroBull"].map({True: "#4ADE80", False: "#F87171"})
        return d


def create_regime_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    d = RegimeDetector().detect(df)
    d["BTC"] = d["Bitcoin"]
    d["GOLD"] = d["Altin"]
    return d
