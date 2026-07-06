import pandas as pd


class IndicatorEngine:

    #######################################################

    @staticmethod
    def sma(series, length):

        return series.rolling(length).mean()

    #######################################################

    @staticmethod
    def ema(series, length):

        return series.ewm(span=length).mean()

    #######################################################

    @staticmethod
    def ratio(a, b):

        return a / b

    #######################################################

    @staticmethod
    def pct(series):

        return series.pct_change()

    #######################################################

    @staticmethod
    def returns(series):

        return series.pct_change().fillna(0)
