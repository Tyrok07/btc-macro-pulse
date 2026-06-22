import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0B0E14; color: #E6E9EF; }

.lk-shell { max-width: 1600px; margin: 0 auto; }
.lk-header {
    padding: 26px 8px 18px 8px;
    border-bottom: 1px solid #1E2430;
    margin-bottom: 22px;
}
.lk-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #6FE3B5;
    margin-bottom: 6px;
}
.lk-title {
    font-size: 32px;
    font-weight: 700;
    color: #F2F4F8;
    margin: 0;
    letter-spacing: -0.01em;
}
.lk-subtitle { font-size: 14px; color: #7C8595; margin-top: 6px; }

.lk-panel {
    background: #0F131C;
    border: 1px solid #1E2430;
    border-radius: 16px;
    padding: 18px 18px 14px 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.18);
}

div[data-testid="stMetric"] {
    background: #131722;
    border: 1px solid #1E2430;
    border-radius: 12px;
    padding: 14px 16px;
}
div[data-testid="stMetric"] label {
    color: #7C8595 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px !important;
    color: #F2F4F8 !important;
}

.lk-regime {
    border-radius: 14px;
    padding: 14px 16px;
    border: 1px solid;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 13px;
    line-height: 1.6;
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
}
.lk-regime-strong-on  { background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.5);  color: #4ADE80; }
.lk-regime-weak-on    { background: rgba(234,179,8,0.10);  border-color: rgba(234,179,8,0.4);  color: #FCD34D; }
.lk-regime-weak-off   { background: rgba(249,115,22,0.10); border-color: rgba(249,115,22,0.4); color: #FB923C; }
.lk-regime-strong-off { background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.4); color: #F87171; }

.lk-section {
    font-size: 15px;
    font-weight: 600;
    color: #F2F4F8;
    margin: 22px 0 12px 0;
    padding-left: 10px;
    border-left: 3px solid #6FE3B5;
}

.lk-card {
    background: #0F131C;
    border: 1px solid #1E2430;
    border-radius: 16px;
    padding: 16px 16px 12px 16px;
}

.lk-ai-box {
    background: #131722;
    border: 1px solid #1E2430;
    border-radius: 12px;
    padding: 20px 22px;
    line-height: 1.75;
    font-size: 15px;
    color: #C8CDD8;
}
.lk-ai-box b, .lk-ai-box strong { color: #F2F4F8; }

.small-note { color: #7C8595; font-size: 12px; }

.stButton > button {
    background: #131722;
    border: 1px solid #2A3140;
    color: #E6E9EF;
    border-radius: 8px;
    font-weight: 500;
    padding: 8px 18px;
}
.stButton > button:hover { border-color: #6FE3B5; color: #6FE3B5; }

.stTextInput input {
    background: #131722;
    border: 1px solid #1E2430;
    color: #E6E9EF;
    border-radius: 8px;
}

[data-testid="stDataFrame"] {
    border: 1px solid #1E2430;
    border-radius: 12px;
    overflow: hidden;
}
</style>

<div class="lk-shell">
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / XCUUSD / BTCUSD · Likidite Kompoziti · 8 Yıllık Analiz</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Altın · Bakır · Bitcoin rasyosu üzerinden likidite yönü, rejim ve BTC fırsatlarını takip et</p>
</div>
</div>
""", unsafe_allow_html=True)

GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()

def telegram_gonder(mesaj):
    if not TOKEN or not CHAT_ID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"},
            timeout=10
        )
        return r.ok
    except Exception:
        return False

@st.cache_data(ttl=3600)
def verileri_getir():
    semboller = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
    df = yf.download(
        list(semboller.keys()),
        period="8y",
        interval="1d",
        auto_adjust=False,
        group_by="column",
        multi_level_index=False,
        progress=False
    )
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            df = df["Close"].copy()
        else:
            df.columns = df.columns.get_level_values(0)
    if "Close" in df.columns:
        close_df = df["Close"].copy()
    else:
        close_df = df.copy()
    if isinstance(close_df, pd.Series):
        close_df = close_df.to_frame()
    rename_map = {c: semboller[c] for c in close_df.columns if c in semboller}
    close_df = close_df.rename(columns=rename_map)
    gerekli = ["Altin", "Bakir", "Bitcoin"]
    if not all(col in close_df.columns for col in gerekli):
        raise ValueError(f"Eksik kolonlar: {set(gerekli) - set(close_df.columns)} | Gelen kolonlar: {list(close_df.columns)}")
    return close_df[gerekli].ffill().bfill()

def gemini_api(prompt):
    if not GEMINI_KEY:
        return None
    modeller = ["gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-2.0-flash"]
    for model in modeller:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            body = {"contents": [{"parts": [{"text": prompt}]}]}
            r = requests.post(url, json=body, timeout=20)
            if r.status_code == 429:
                continue
            r.raise_for_status()
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    return "⚠️ Tüm modeller şu an meşgul. Lütfen kısa süre sonra yeniden deneyin."

@st.cache_data(ttl=1800)
def gemini_yorum_cache(btc_fiyat_r, rejim_etiketi, kazanc, bh_kazanc, strateji_deger, bh_deger, kisa_bull, makro_bull):
    prompt = f"""
Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının anlayabileceği,
sade Türkçe ile 4-6 cümlelik bir özet yorum yaz. Teknik jargon kullanma.
Grafik, rasyo, SMA gibi terimleri açıkla. Sonunda tek cümleyle "Şu an ne yapmalı?" önerisi ver.

MEVCUT VERİLER:
- Bitcoin Fiyatı: ${btc_fiyat_r:,.0f}
- Mevcut Piyasa Rejimi: {rejim_etiketi}
- Kısa Vade (SMA10): {'Boğa — kısa vadede BTC lehine akış var' if kisa_bull else 'Ayı — kısa vadede BTC aleyhine akış var'}
- Uzun Vade (SMA50): {'Boğa — büyük döngü yukarı' if makro_bull else 'Ayı — büyük döngü aşağı'}
- 8 Yıllık Strateji Kazancı: %{kazanc:+.1f} (${strateji_deger:,.0f})
- BTC Al-Tut Kazancı (kıyas): %{bh_kazanc:+.1f} (${bh_deger:,.0f})

Yanıtın sadece yorum metni olsun, başlık veya madde işareti ekleme.
"""
    return gemini_api(prompt)

def format_pct(x):
    return f"%{x:+.1f}"

try:
    data = verileri_getir()

    if data.empty or len(data) < 60:
        st.error("Veri havuzu henüz yeterli büyüklükte değil.")
        st.stop()

    data["Rasyo"] = data["Altin"] / (data["Bakir"] * data["Bitcoin"])
    data["SMA10"] = data["Rasyo"].rolling(window=10).mean()
    data["SMA50"] = data["Rasyo"].rolling(window=50).mean()
    data = data.dropna().copy()

    son_rasyo = data["Rasyo"].iloc[-1]
    sma10 = data["SMA10"].iloc[-1]
    sma50 = data["SMA50"].iloc[-1]
    btc_fiyat = data["Bitcoin"].iloc[-1]
    altin_fiyat = data["Altin"].iloc[-1]
    bakir_fiyat = data["Bakir"].iloc[-1]

    makro_bull = son_rasyo < sma50
    kisa_bull = son_rasyo < sma10

    if makro_bull and kisa_bull:
        rejim_kodu = "strong_on"
        rejim_etiketi = "🟢🟢 GÜÇLÜ BOĞA"
        rejim_aciklama = "Her iki sinyal de BTC lehine · En güçlü alım bölgesi"
        status_text = "🟢🟢 GÜÇLÜ BOĞA — Her iki sinyal BTC lehine"
    elif makro_bull and not kisa_bull:
        rejim_kodu = "weak_on"
        rejim_etiketi = "🟡🟢 BOĞA + Kısa Düzeltme"
        rejim_aciklama = "Büyük trend yukarı · Kısa vadede hafif baskı"
        status_text = "🟡🟢 BOĞA TRENDİ — Kısa vadeli düzeltme içinde"
    elif not makro_bull and kisa_bull:
        rejim_kodu = "weak_off"
        rejim_etiketi = "🟠🔴 AYI + Kısa Toparlanma"
        rejim_aciklama = "Büyük trend aşağı · Kısa vadede geçici rahatlama"
        status_text = "🟠🔴 AYI TRENDİ — Kısa vadeli toparlanma içinde"
    else:
        rejim_kodu = "strong_off"
        rejim_etiketi = "🔴🔴 GÜÇLÜ AYI"
        rejim_aciklama = "Her iki sinyal de BTC aleyhine · En güçlü kaçış bölgesi"
        status_text = "🔴🔴 GÜÇLÜ AYI — Her iki sinyal BTC aleyhine"

    ilk_btc = data["Bitcoin"].iloc[0]
    bh_adet = 10000.0 / ilk_btc
    data["BuyHold"] = bh_adet * data["Bitcoin"]
    bh_son = data["BuyHold"].iloc[-1]
    bh_kazanc = (bh_son - 10000.0) / 10000.0 * 100

    toplam = 10000.0
    btc_adet_r = 0.0
    altin_adet_r = 0.0
    nakit_r = toplam
    gunluk_rot = []
    gunluk_btc_pct = []
    gunluk_altin_pct = []
    rejim_serisi = []

    for i in range(len(data)):
        r = data["Rasyo"].iloc[i]
        s10 = data["SMA10"].iloc[i]
        s50 = data["SMA50"].iloc[i]
        fbtc = data["Bitcoin"].iloc[i]
        falt = data["Altin"].iloc[i]

        iki_boga = (r < s10) and (r < s50)
        karma_boga = (r < s50) and (r >= s10)

        port_deger = nakit_r + btc_adet_r * fbtc + altin_adet_r * falt

        if iki_boga:
            btc_adet_r = port_deger / fbtc
            altin_adet_r = 0.0
            nakit_r = 0.0
            btc_pct, alt_pct = 100, 0
            rejim = "Güçlü Boğa"
        elif karma_boga:
            btc_adet_r = (port_deger * 0.5) / fbtc
            altin_adet_r = (port_deger * 0.5) / falt
            nakit_r = 0.0
            btc_pct, alt_pct = 50, 50
            rejim = "Boğa + Düzeltme"
        else:
            btc_adet_r = 0.0
            altin_adet_r = port_deger / falt
            nakit_r = 0.0
            btc_pct, alt_pct = 0, 100
            rejim = "Altın Ağırlık"

        gunluk_rot.append(port_deger)
        gunluk_btc_pct.append(btc_pct)
        gunluk_altin_pct.append(alt_pct)
        rejim_serisi.append(rejim)

    data["Rotasyon"] = gunluk_rot
    data["BTC_Pct"] = gunluk_btc_pct
    data["Altin_Pct"] = gunluk_altin_pct
    data["Rejim"] = rejim_serisi

    rot_son = data["Rotasyon"].iloc[-1]
    rot_kazanc = (rot_son - 10000.0) / 10000.0 * 100
    su_an_btc_pct = data["BTC_Pct"].iloc[-1]
    su_an_altin_pct = data["Altin_Pct"].iloc[-1]

    son_90 = data.tail(90).copy()
    tablo_tarihsel = son_90[["Bitcoin", "Altin", "Bakir", "Rasyo", "SMA10", "SMA50", "BTC_Pct", "Altin_Pct", "Rejim"]].copy()
    tablo_tarihsel.index = tablo_tarihsel.index.strftime("%Y-%m-%d")
    tablo_tarihsel = tablo_tarihsel.reset_index().rename(columns={"index": "Tarih"})

    col_a, col_b, col_c, col_d = st.columns([1.2, 1, 1, 1])
    col_a.metric("Bitcoin Fiyatı", f"${btc_fiyat:,.0f}", f"{format_pct((btc_fiyat / data['Bitcoin'].iloc[-2] - 1) * 100)} son gün")
    col_b.metric("Altın Fiyatı", f"${altin_fiyat:,.0f}", f"{format_pct((altin_fiyat / data['Altin'].iloc[-2] - 1) * 100)} son gün")
    col_c.metric("8Y Rotasyon", f"${rot_son:,.0f}", f"{format_pct(rot_kazanc)}")
    col_d.metric("BTC Al-Tut", f"${bh_son:,.0f}", f"{format_pct(bh_kazanc)}")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown(f"""
<div class="lk-regime lk-regime-{rejim_kodu.replace('_','-')}">
    <span>{rejim_etiketi}</span>
    <span style="font-weight:400; font-size:12px; color:#7C8595">{rejim_aciklama}</span>
    <span style="margin-left:auto; font-size:13px; color:#E6E9EF;">
        Şu an: <b style="color:#F0B90B">BTC %{su_an_btc_pct:.0f}</b>
        &nbsp;·&nbsp;
        <b style="color:#E5C07B">Altın %{su_an_altin_pct:.0f}</b>
    </span>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if rot_son > bh_son:
        st.success(f"✅ Rotasyon stratejisi al-tutun **${rot_son - bh_son:,.0f}** önünde  ·  Rotasyon {format_pct(rot_kazanc)}  vs  Al-Tut {format_pct(bh_kazanc)}")
    else:
        st.warning(f"Rotasyon stratejisi al-tuta kıyasla **${bh_son - rot_son:,.0f}** geride  ·  Rotasyon {format_pct(rot_kazanc)}  vs  Al-Tut {format_pct(bh_kazanc)}")

    st.markdown('<div class="lk-section">Likidite Rasyosu · SMA10 · SMA50 · BTC Fiyatı</div>', unsafe_allow_html=True)
    left, right = st.columns([1.7, 0.9], gap="large")

    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data.index, y=data["Rasyo"],
            name="Süper Rasyo",
            line=dict(color="#7C8595", width=1.0),
            opacity=0.75
        ))

        data["Renk10"] = data.apply(lambda r: "#4ADE80" if r["Rasyo"] < r["SMA10"] else "#F87171", axis=1)
        for _, grp in data.groupby((data["Renk10"] != data["Renk10"].shift()).cumsum()):
            fig.add_trace(go.Scatter(
                x=grp.index, y=grp["SMA10"],
                mode="lines",
                line=dict(color=grp["Renk10"].iloc[0], width=1.4, dash="dot"),
                showlegend=False
            ))

        data["Renk50"] = data.apply(lambda r: "#4ADE80" if r["Rasyo"] < r["SMA50"] else "#F87171", axis=1)
        for _, grp in data.groupby((data["Renk50"] != data["Renk50"].shift()).cumsum()):
            fig.add_trace(go.Scatter(
                x=grp.index, y=grp["SMA50"],
                mode="lines",
                line=dict(color=grp["Renk50"].iloc[0], width=2.4),
                showlegend=False
            ))

        fig.add_trace(go.Scatter(
            x=data.index, y=data["Bitcoin"],
            name="BTC Fiyatı",
            line=dict(color="#F0B90B", width=1.2, dash="dot"),
            yaxis="y2"
        ))

        fig.update_layout(
            height=560,
            template="plotly_dark",
            paper_bgcolor="#0F131C",
            plot_bgcolor="#0F131C",
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor="#1E2430", linecolor="#1E2430"),
            yaxis=dict(title="Süper Rasyo", gridcolor="#1E2430", title_font=dict(color="#7C8595"), tickfont=dict(color="#7C8595")),
            yaxis2=dict(title="BTC (USD)", overlaying="y", side="right", title_font=dict(color="#F0B90B"), tickfont=dict(color="#F0B90B"), gridcolor='rgba(0,0,0,0)'),
            legend=dict(orientation="h", y=1.03, x=1, xanchor="right", bgcolor='rgba(0,0,0,0)', font=dict(size=11))
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown('<div class="lk-card">', unsafe_allow_html=True)
        st.markdown("**Güncel Özet**")
        ozet_df = pd.DataFrame({
            "Alan": ["Rejim", "SMA10", "SMA50", "Rasyo", "BTC Payı", "Altın Payı"],
            "Değer": [rejim_etiketi, f"{sma10:.4e}", f"{sma50:.4e}", f"{son_rasyo:.4e}", f"%{su_an_btc_pct:.0f}", f"%{su_an_altin_pct:.0f}"]
        })
        st.dataframe(ozet_df, use_container_width=True, hide_index=True)
        st.markdown("<div class='small-note'>Bu tablo, grafikteki renklendirmeyi tek bakışta anlaşılır hale getirir.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="lk-card">', unsafe_allow_html=True)
        st.markdown("**Son 10 Günlük Rejim Geçişi**")
        giris_df = data.tail(10)[["Bitcoin", "Altin", "Rasyo", "SMA10", "SMA50", "BTC_Pct", "Altin_Pct", "Rejim"]].copy()
        giris_df.index = giris_df.index.strftime("%Y-%m-%d")
        giris_df = giris_df.reset_index().rename(columns={"index": "Tarih"})
        st.dataframe(giris_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="lk-section">Rotasyon Stratejisi vs BTC Al-Tut · Giriş $10.000</div>', unsafe_allow_html=True)
    left2, right2 = st.columns([1.55, 1], gap="large")

    with left2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=data.index, y=data["Rotasyon"], name="BTC+Altın Rotasyon", line=dict(color="#6FE3B5", width=2.6)))
        fig2.add_trace(go.Scatter(x=data.index, y=data["BuyHold"], name="BTC Al-Tut", line=dict(color="#F0B90B", width=1.4, dash="dot")))
        fig2.update_layout(
            height=380,
            template="plotly_dark",
            paper_bgcolor="#0F131C",
            plot_bgcolor="#0F131C",
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor="#1E2430"),
            yaxis=dict(title="Portföy Değeri (USD)", gridcolor="#1E2430", title_font=dict(color="#7C8595"), tickfont=dict(color="#7C8595")),
            legend=dict(orientation="h", y=1.03, x=1, xanchor="right", bgcolor='rgba(0,0,0,0)')
        )
        st.plotly_chart(fig2, use_container_width=True)

    with right2:
        st.markdown('<div class="lk-card">', unsafe_allow_html=True)
        portfoy_df = pd.DataFrame({
            "Karşılaştırma": ["Başlangıç", "Rotasyon Son", "Al-Tut Son", "Fark", "Rotasyon Getiri", "Al-Tut Getiri"],
            "Değer": [
                "$10,000",
                f"${rot_son:,.0f}",
                f"${bh_son:,.0f}",
                f"${rot_son - bh_son:,.0f}",
                f"%{rot_kazanc:+.1f}",
                f"%{bh_kazanc:+.1f}"
            ]
        })
        st.markdown("**Portföy Özeti**")
        st.dataframe(portfoy_df, use_container_width=True, hide_index=True)
        st.markdown("<div class='small-note'>Bu tablo, grafiğin altındaki mutlak performans farkını sayısal olarak netleştirir.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="lk-section">Portföy Dağılımı · BTC vs Altın Ağırlığı (%)</div>', unsafe_allow_html=True)
    left3, right3 = st.columns([1.35, 1], gap="large")

    with left3:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=data.index, y=data["BTC_Pct"],
            name="BTC Ağırlığı %",
            line=dict(color="#F0B90B", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(240,185,11,0.15)"
        ))
        fig3.add_trace(go.Scatter(
            x=data.index, y=data["Altin_Pct"],
            name="Altın Ağırlığı %",
            line=dict(color="#E5C07B", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(229,192,123,0.10)"
        ))
        fig3.update_layout(
            height=260,
            template="plotly_dark",
            paper_bgcolor="#0F131C",
            plot_bgcolor="#0F131C",
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor="#1E2430"),
            yaxis=dict(title="%", gridcolor="#1E2430", range=[0, 110], title_font=dict(color="#7C8595"), tickfont=dict(color="#7C8595")),
            legend=dict(orientation="h", y=1.08, x=1, xanchor="right", bgcolor='rgba(0,0,0,0)')
        )
        st.plotly_chart(fig3, use_container_width=True)

    with right3:
        st.markdown('<div class="lk-card">', unsafe_allow_html=True)
        dagilim_df = pd.DataFrame({
            "Alan": ["Şu An BTC", "Şu An Altın", "Kısa Vade", "Uzun Vade"],
            "Değer": [
                f"%{su_an_btc_pct:.0f}",
                f"%{su_an_altin_pct:.0f}",
                "Boğa" if kisa_bull else "Ayı",
                "Boğa" if makro_bull else "Ayı"
            ]
        })
        st.markdown("**Dağılım ve Sinyal**")
        st.dataframe(dagilim_df, use_container_width=True, hide_index=True)
        st.markdown("<div class='small-note'>Yüzde dağılımı, portföyün neden hangi varlığa kaydığını hızlıca gösterir.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="lk-section">Yapay Zeka Piyasa Yorumu</div>', unsafe_allow_html=True)
    if GEMINI_KEY:
        with st.spinner("Piyasa verileri yorumlanıyor..."):
            yorum = gemini_yorum_cache(
                round(btc_fiyat / 500) * 500,
                rejim_etiketi,
                rot_kazanc,
                bh_kazanc,
                rot_son,
                bh_son,
                kisa_bull,
                makro_bull
            )
        if yorum:
            st.markdown(f'<div class="lk-ai-box">{yorum}</div>', unsafe_allow_html=True)
    else:
        st.info("Otomatik yorum için Streamlit secrets'a `GEMINI_API_KEY` ekleyin.")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    user_soru = st.text_input(
        "Soru sor",
        label_visibility="collapsed",
        placeholder="Aklınıza takılan bir şey mi var? Buraya yazın..."
    )
    if user_soru and GEMINI_KEY:
        with st.spinner("Yanıt hazırlanıyor..."):
            baglam = f"""
Sen bir piyasa analisti danışmanısın. Şu anki durum:
- BTC: ${btc_fiyat:,.0f}
- Rejim: {rejim_etiketi}
- Kısa vade (SMA10): {'Boğa' if kisa_bull else 'Ayı'}
- Uzun vade (SMA50): {'Boğa' if makro_bull else 'Ayı'}
- 8Y Strateji: %{rot_kazanc:+.1f}  |  Al-Tut: %{bh_kazanc:+.1f}

Sıradan bir yatırımcıya sade Türkçe ile, kısa ve net yanıt ver. Teknik terimler kullanma.
Kullanıcı sorusu: {user_soru}
"""
            yanit = gemini_api(baglam)
            if yanit:
                st.markdown(f'<div class="lk-ai-box">{yanit}</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    if st.button("Güncel Durumu Telegram'a Gönder"):
        rapor = (
            f"◆ *LİKİDİTE KOMPOZİT PANELİ* ◆\n\n"
            f"🪙 BTC: ${btc_fiyat:,.0f}\n"
            f"🥇 Altın: ${altin_fiyat:,.0f}\n"
            f"🥈 Bakır: ${bakir_fiyat:,.0f}\n"
            f"📊 Rejim: {status_text}\n"
            f"  • Kısa Vade: {'🟢 Boğa' if kisa_bull else '🔴 Ayı'}\n"
            f"  • Uzun Vade: {'🟢 Boğa' if makro_bull else '🔴 Ayı'}\n\n"
            f"💼 Şu An: BTC %{su_an_btc_pct:.0f} · Altın %{su_an_altin_pct:.0f}\n"
            f"📈 8Y Rotasyon: ${rot_son:,.0f} (%{rot_kazanc:+.1f})\n"
            f"📊 Al-Tut Kıyas: ${bh_son:,.0f} (%{bh_kazanc:+.1f})"
        )
        if telegram_gonder(rapor):
            st.success("Telegram'a gönderildi.")
        else:
            st.warning("Telegram bilgileri eksik veya hatalı.")

    st.markdown('<div class="lk-section">Son 90 Gün Detay Tablosu</div>', unsafe_allow_html=True)
    tablo_show = son_90[["Altin", "Bakir", "Bitcoin", "Rasyo", "SMA10", "SMA50", "BTC_Pct", "Altin_Pct", "Rejim"]].copy()
    tablo_show.index = tablo_show.index.strftime("%Y-%m-%d")
    tablo_show = tablo_show.reset_index().rename(columns={"index": "Tarih"})
    st.dataframe(tablo_show, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Genel hata: {e}")
