from dataclasses import dataclass


@dataclass
class TargetAllocation:

    btc: float

    gold: float

    cash: float = 0.0


class Rebalancer:

    def rebalance(
            self,
            portfolio,
            target,
            btc_price,
            gold_price,
            date):

        total = portfolio.total_value(
            btc_price,
            gold_price
        )

        target_btc = total * target.btc

        target_gold = total * target.gold

        current_btc = portfolio.btc_qty * btc_price

        current_gold = portfolio.gold_qty * gold_price

        ################################################

        btc_diff = target_btc - current_btc

        gold_diff = target_gold - current_gold

        ################################################

        if btc_diff < 0:

            portfolio.sell(

                date,

                "BTC",

                abs(btc_diff) / btc_price,

                btc_price

            )

        if gold_diff < 0:

            portfolio.sell(

                date,

                "GOLD",

                abs(gold_diff) / gold_price,

                gold_price

            )

        ################################################

        if btc_diff > 0:

            portfolio.buy(

                date,

                "BTC",

                btc_diff,

                btc_price

            )

        if gold_diff > 0:

            portfolio.buy(

                date,

                "GOLD",

                gold_diff,

                gold_price

            )
