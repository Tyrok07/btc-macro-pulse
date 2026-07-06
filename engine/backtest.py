from dataclasses import dataclass
import pandas as pd

from engine.portfolio import Portfolio
from engine.rebalance import Rebalancer, TargetAllocation


@dataclass
class BacktestResult:
    equity_curve: list
    trades: list
    portfolio: Portfolio


class BacktestEngine:

    def __init__(
        self,
        initial_cash=10000,
        btc_fee=0.001,
        gold_fee=0.001,
        slippage=0.0005
    ):

        self.portfolio = Portfolio(
            initial_cash=initial_cash,
            btc_fee=btc_fee,
            gold_fee=gold_fee,
            slippage=slippage
        )

        self.rebalancer = Rebalancer()

    ###################################################################

    def target_from_regime(self, regime):

        if regime == "Güçlü Boğa":
            return TargetAllocation(
                btc=1.0,
                gold=0.0
            )

        elif regime == "Boğa":
            return TargetAllocation(
                btc=0.75,
                gold=0.25
            )

        elif regime == "Nötr":
            return TargetAllocation(
                btc=0.50,
                gold=0.50
            )

        elif regime == "Ayı":

            return TargetAllocation(
                btc=0.25,
                gold=0.75
            )

        else:

            return TargetAllocation(
                btc=0.0,
                gold=1.0
            )

    ###################################################################

    def run(self, df: pd.DataFrame):

        previous_regime = None

        for date, row in df.iterrows():

            btc_price = row["BTC"]

            gold_price = row["GOLD"]

            regime = row["Regime"]

            if previous_regime is None:

                target = self.target_from_regime(regime)

                self.rebalancer.rebalance(

                    self.portfolio,

                    target,

                    btc_price,

                    gold_price,

                    date

                )

                previous_regime = regime

            elif regime != previous_regime:

                target = self.target_from_regime(regime)

                self.rebalancer.rebalance(

                    self.portfolio,

                    target,

                    btc_price,

                    gold_price,

                    date

                )

                previous_regime = regime

            self.portfolio.snapshot(

                btc_price,

                gold_price

            )

        return BacktestResult(

            equity_curve=self.portfolio.equity_curve,

            trades=self.portfolio.trades,

            portfolio=self.portfolio

        )
