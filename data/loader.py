import pandas as pd
import streamlit as st
import yfinance as yf


class DataLoader:

    SYMBOLS = {
        "GC=F": "Altin",
        "HG=F": "Bakir",
        "BTC-USD": "Bitcoin"
    }

    @staticmethod
    @st.cache_data(ttl=3600)
    def load():

        df = yf.download(
            list(DataLoader.SYMBOLS.keys()),
            period="8y",
            interval="1d",
            auto_adjust=False,
            multi_level_index=False,
            progress=False
        )

        if df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):

            if "Close" in df.columns.get_level_values(0):
                df = df["Close"].copy()
            else:
                df = df.set_axis(
                    df.columns.get_level_values(0),
                    axis=1
                )

        elif "Close" in df.columns:

            df = df["Close"]

        df = df.rename(columns={
            k: v
            for k, v in DataLoader.SYMBOLS.items()
            if k in df.columns
        })

        cols = [
            c for c in [
                "Altin",
                "Bakir",
                "Bitcoin"
            ]
            if c in df.columns
        ]

        return df[cols].ffill().bfill()
