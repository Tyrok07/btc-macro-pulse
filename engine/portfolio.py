from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Trade:
    date: str
    asset: str
    side: str
    quantity: float
    price: float
    value: float
    fee: float
    slippage: float
    portfolio_value: float


@dataclass
class Portfolio:
    initial_cash: float = 10000.0
    commission: float = 0.0
    slippage: float = 0.0
    cash: float = field(init=False)
    btc_qty: float = 0.0
    gold_qty: float = 0.0
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = float(self.initial_cash)

    def buy(self, date, asset: str, amount_cash: float, price: float) -> Trade | None:
        if amount_cash <= 0 or price <= 0:
            return None
        amount_cash = min(float(amount_cash), self.cash)
        fee = amount_cash * self.commission
        slip = amount_cash * self.slippage
        invest = max(amount_cash - fee - slip, 0.0)
        quantity = invest / float(price)
        self.cash -= amount_cash
        if asset == "BTC":
            self.btc_qty += quantity
        elif asset == "GOLD":
            self.gold_qty += quantity
        else:
            raise ValueError(f"Unsupported asset: {asset}")
        trade = Trade(str(date), asset, "BUY", quantity, float(price), invest, fee, slip, 0.0)
        self.trades.append(trade)
        return trade

    def sell(self, date, asset: str, quantity: float, price: float) -> Trade | None:
        if quantity <= 0 or price <= 0:
            return None
        if asset == "BTC":
            quantity = min(float(quantity), self.btc_qty)
            self.btc_qty -= quantity
        elif asset == "GOLD":
            quantity = min(float(quantity), self.gold_qty)
            self.gold_qty -= quantity
        else:
            raise ValueError(f"Unsupported asset: {asset}")
        gross = quantity * float(price)
        fee = gross * self.commission
        slip = gross * self.slippage
        net = max(gross - fee - slip, 0.0)
        self.cash += net
        trade = Trade(str(date), asset, "SELL", quantity, float(price), net, fee, slip, 0.0)
        self.trades.append(trade)
        return trade

    def total_value(self, btc_price: float, gold_price: float) -> float:
        return self.cash + self.btc_qty * float(btc_price) + self.gold_qty * float(gold_price)

    def snapshot(self, btc_price: float, gold_price: float) -> float:
        value = self.total_value(btc_price, gold_price)
        self.equity_curve.append(value)
        if self.trades:
            self.trades[-1].portfolio_value = value
        return value

    def allocation(self, btc_price: float, gold_price: float) -> Dict[str, float]:
        total = self.total_value(btc_price, gold_price)
        if total == 0:
            return {"cash": 0.0, "btc": 0.0, "gold": 0.0}
        return {
            "cash": self.cash / total,
            "btc": self.btc_qty * float(btc_price) / total,
            "gold": self.gold_qty * float(gold_price) / total,
        }

    def reset(self) -> None:
        self.cash = float(self.initial_cash)
        self.btc_qty = 0.0
        self.gold_qty = 0.0
        self.trades.clear()
        self.equity_curve.clear()
