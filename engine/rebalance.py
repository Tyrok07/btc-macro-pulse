from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetAllocation:
    btc: float
    gold: float
    cash: float = 0.0


class Rebalancer:
    def __init__(self, partial_rebalance: float = 1.0) -> None:
        if not 0 < partial_rebalance <= 1:
            raise ValueError("partial_rebalance must be in the interval (0, 1].")
        self.partial_rebalance = float(partial_rebalance)

    def rebalance(self, portfolio, target: TargetAllocation, btc_price: float, gold_price: float, date) -> float:
        total = portfolio.total_value(btc_price, gold_price)
        target_btc = total * float(target.btc)
        target_gold = total * float(target.gold)
        current_btc = portfolio.btc_qty * float(btc_price)
        current_gold = portfolio.gold_qty * float(gold_price)
        btc_diff = (target_btc - current_btc) * self.partial_rebalance
        gold_diff = (target_gold - current_gold) * self.partial_rebalance

        if btc_diff < 0:
            portfolio.sell(date, "BTC", abs(btc_diff) / float(btc_price), btc_price)
        if gold_diff < 0:
            portfolio.sell(date, "GOLD", abs(gold_diff) / float(gold_price), gold_price)
        if btc_diff > 0:
            portfolio.buy(date, "BTC", btc_diff, btc_price)
        if gold_diff > 0:
            portfolio.buy(date, "GOLD", gold_diff, gold_price)
        return portfolio.total_value(btc_price, gold_price)
