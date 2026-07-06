from dataclasses import dataclass


@dataclass
class CommissionModel:
    """
    Handles transaction costs.

    fee = exchange commission

    slippage = execution cost
    """

    btc_fee: float = 0.001
    gold_fee: float = 0.001

    slippage: float = 0.0005

    def fee_rate(self, asset: str) -> float:

        asset = asset.upper()

        if asset == "BTC":
            return self.btc_fee

        if asset == "GOLD":
            return self.gold_fee

        raise ValueError(f"Unknown asset: {asset}")

    def calculate_buy(self,
                      asset: str,
                      amount: float):

        fee = amount * self.fee_rate(asset)

        slip = amount * self.slippage

        total = fee + slip

        return {

            "fee": fee,

            "slippage": slip,

            "cost": total,

            "net": amount - total

        }

    def calculate_sell(self,
                       asset: str,
                       amount: float):

        fee = amount * self.fee_rate(asset)

        slip = amount * self.slippage

        total = fee + slip

        return {

            "fee": fee,

            "slippage": slip,

            "cost": total,

            "net": amount - total

        }
