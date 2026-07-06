import yfinance as yf
import pandas as pd


class DataLoader:

    def __init__(self):

        self.cache = {}

    ########################################################

    def download(
        self,
        ticker,
        start,
        end,
        interval="1d"
    ):

        df = yf.download(
            ticker,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            raise ValueError(f"{ticker} data not found.")

        return df

    ########################################################

    def close(
        self,
        ticker,
        start,
        end,
        interval="1d"
    ):

        df = self.download(
            ticker,
            start,
            end,
            interval
        )

        return df["Close"].rename(ticker)

    ########################################################

    def merge(self, series):

        return pd.concat(series, axis=1).dropna()
