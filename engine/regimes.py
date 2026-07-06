import pandas as pd


def rejim_tespit(r, s10, s50):
    """
    Girdi : rasyo, SMA10, SMA50
    Çıktı : (isim, btc_pct, alt_pct, css_kodu, emoji_etiket, açıklama)
    """
    if r < s10 and r < s50:
        return (
            "Güçlü Boğa",
            100,
            0,
            "strong-on",
            "🟢🟢 GÜÇLÜ BOĞA",
            "Her iki sinyal BTC lehine · En güçlü alım bölgesi",
        )

    elif r < s50:
        return (
            "Boğa + Düzeltme",
            50,
            50,
            "weak-on",
            "🟡🟢 BOĞA + Kısa Düzeltme",
            "Büyük trend yukarı · Kısa vadede hafif baskı",
        )

    elif r < s10:
        return (
            "Ayı + Toparlanma",
            0,
            100,
            "weak-off",
            "🟠🔴 AYI + Kısa Toparlanma",
            "Büyük trend aşağı · Kısa vadede geçici rahatlama",
        )

    else:
        return (
            "Güçlü Ayı",
            0,
            100,
            "strong-off",
            "🔴🔴 GÜÇLÜ AYI",
            "Her iki sinyal BTC aleyhine · Altın koruma modu",
        )


def create_regime_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    BacktestEngine'in kullanacağı dataframe'i hazırlar.

    Giriş:
        Altin
        Bakir
        Bitcoin

    Çıkış:
        Altin
        Bakir
        Bitcoin
        Rasyo
        SMA10
        SMA50
        Regime
        BTC
        GOLD
    """

    d = df.copy()

    d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()

    d = d.dropna().copy()

    regimes = []

    for _, row in d.iterrows():

        isim, *_ = rejim_tespit(
            row["Rasyo"],
            row["SMA10"],
            row["SMA50"],
        )

        regimes.append(isim)

    d["Regime"] = regimes

    # Yeni BacktestEngine'in beklediği kolonlar
    d["BTC"] = d["Bitcoin"]
    d["GOLD"] = d["Altin"]

    return d
