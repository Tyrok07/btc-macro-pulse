from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:

    total_return: float
    cagr: float
    annual_volatility: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    recovery_factor: float


class MetricsEngine:

    def __init__(self, risk_free_rate=0.0):

        self.risk_free_rate = risk_free_rate

    ####################################################################

    def max_drawdown(self, equity):

        equity = np.asarray(equity)

        running_max = np.maximum.accumulate(equity)

        drawdown = equity / running_max - 1

        return float(drawdown.min())

    ####################################################################

    def CAGR(self, equity):

        years = len(equity) / 365.25

        if years <= 0:

            return 0

        return (equity[-1] / equity[0]) ** (1 / years) - 1

    ####################################################################

    def daily_returns(self, equity):

        equity = pd.Series(equity)

        return equity.pct_change().dropna()

    ####################################################################

    def annual_volatility(self, returns):

        return returns.std() * np.sqrt(365)

    ####################################################################

    def sharpe_ratio(self, returns):

        excess = returns - self.risk_free_rate / 365

        std = excess.std()

        if std == 0:

            return 0

        return np.sqrt(365) * excess.mean() / std

    ####################################################################

    def sortino_ratio(self, returns):

        downside = returns[returns < 0]

        if len(downside) == 0:

            return 0

        downside_std = downside.std()

        if downside_std == 0:

            return 0

        return np.sqrt(365) * returns.mean() / downside_std

    ####################################################################

    def calmar_ratio(self, cagr, max_dd):

        if max_dd == 0:

            return 0

        return cagr / abs(max_dd)

    ####################################################################

    def recovery_factor(self,
                        total_return,
                        max_dd):

        if max_dd == 0:

            return 0

        return total_return / abs(max_dd)

    ####################################################################

    def evaluate(self,
                 equity):

        returns = self.daily_returns(equity)

        total_return = equity[-1] / equity[0] - 1

        cagr = self.CAGR(equity)

        vol = self.annual_volatility(returns)

        sharpe = self.sharpe_ratio(returns)

        sortino = self.sortino_ratio(returns)

        max_dd = self.max_drawdown(equity)

        calmar = self.calmar_ratio(cagr, max_dd)

        recovery = self.recovery_factor(

            total_return,

            max_dd

        )

        return PerformanceMetrics(

            total_return=total_return,

            cagr=cagr,

            annual_volatility=vol,

            sharpe=sharpe,

            sortino=sortino,

            calmar=calmar,

            max_drawdown=max_dd,

            recovery_factor=recovery

        )
