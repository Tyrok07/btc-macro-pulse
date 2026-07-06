from dataclasses import dataclass, field
from typing import List, Dict


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

    initial_cash: float

    btc_fee: float = 0.001

    gold_fee: float = 0.001

    slippage: float = 0.0005

    cash: float = field(init=False)

    btc_qty: float = 0.0

    gold_qty: float = 0.0

    trades: List[Trade] = field(default_factory=list)

    equity_curve: List[float] = field(default_factory=list)

    def __post_init__(self):

        self.cash = self.initial_cash

    ###################################################################

    def buy(self,
            date,
            asset,
            amount_cash,
            price):

        if amount_cash <= 0:

            return

        amount_cash = min(amount_cash, self.cash)

        fee_rate = self.btc_fee if asset == "BTC" else self.gold_fee

        fee = amount_cash * fee_rate

        slip = amount_cash * self.slippage

        invest = amount_cash - fee - slip

        qty = invest / price

        self.cash -= amount_cash

        if asset == "BTC":

            self.btc_qty += qty

        else:

            self.gold_qty += qty

        self.trades.append(

            Trade(

                date=date,

                asset=asset,

                side="BUY",

                quantity=qty,

                price=price,

                value=invest,

                fee=fee,

                slippage=slip,

                portfolio_value=0

            )

        )

    ###################################################################

    def sell(
            self,
            date,
            asset,
            quantity,
            price):

        if quantity <= 0:

            return

        if asset == "BTC":

            quantity = min(quantity, self.btc_qty)

            self.btc_qty -= quantity

        else:

            quantity = min(quantity, self.gold_qty)

            self.gold_qty -= quantity

        gross = quantity * price

        fee_rate = self.btc_fee if asset == "BTC" else self.gold_fee

        fee = gross * fee_rate

        slip = gross * self.slippage

        net = gross - fee - slip

        self.cash += net

        self.trades.append(

            Trade(

                date=date,

                asset=asset,

                side="SELL",

                quantity=quantity,

                price=price,

                value=net,

                fee=fee,

                slippage=slip,

                portfolio_value=0

            )

        )

    ###################################################################

    def total_value(
            self,
            btc_price,
            gold_price):

        return (

            self.cash

            + self.btc_qty * btc_price

            + self.gold_qty * gold_price

        )

    ###################################################################

    def snapshot(
            self,
            btc_price,
            gold_price):

        value = self.total_value(

            btc_price,

            gold_price

        )

        self.equity_curve.append(value)

        if len(self.trades):

            self.trades[-1].portfolio_value = value

        return value

    ###################################################################

    def allocation(
            self,
            btc_price,
            gold_price):

        total = self.total_value(

            btc_price,

            gold_price

        )

        if total == 0:

            return {

                "cash": 0,

                "btc": 0,

                "gold": 0

            }

        return {

            "cash": self.cash / total,

            "btc": self.btc_qty * btc_price / total,

            "gold": self.gold_qty * gold_price / total

        }

    ###################################################################

    def reset(self):

        self.cash = self.initial_cash

        self.btc_qty = 0

        self.gold_qty = 0

        self.trades.clear()

        self.equity_curve.clear()
