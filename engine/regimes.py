def rejim_tespit(r, s10, s50):
    """
    Girdi : rasyo, SMA10, SMA50
    Çıktı : (isim, btc_pct, alt_pct, css_kodu, emoji_etiket, açıklama)
    """
    if r < s10 and r < s50:
        return ("Güçlü Boğa",        100, 0,
                "strong-on",  "🟢🟢 GÜÇLÜ BOĞA",
                "Her iki sinyal BTC lehine · En güçlü alım bölgesi")
    elif r < s50:
        return ("Boğa + Düzeltme",   50, 50,
                "weak-on",    "🟡🟢 BOĞA + Kısa Düzeltme",
                "Büyük trend yukarı · Kısa vadede hafif baskı")
    elif r < s10:
        return ("Ayı + Toparlanma",  0, 100,
                "weak-off",   "🟠🔴 AYI + Kısa Toparlanma",
                "Büyük trend aşağı · Kısa vadede geçici rahatlama")
    else:
        return ("Güçlü Ayı",         0, 100,
                "strong-off", "🔴🔴 GÜÇLÜ AYI",
                "Her iki sinyal BTC aleyhine · Altın koruma modu")
