import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json
from pathlib import Path
from datetime import datetime, date

st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ROTATION_LOG_FILE = STATE_DIR / "rotasyon_log.csv"
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

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
""", unsafe_allow_html=True)

GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def load_state():
    if ALERT_STATE_FILE.exists():
        try:
            return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_state(state):
    ALERT_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

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
    return None

@st.cache_data(ttl=1800)
def gemini_yorum_cache(btc_fiyat_r, rejim_etiketi, kazanc, bh_kazanc, strateji_deger, bh_deger, kisa_bull, makro_bull):
    prompt = f"""
Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının anlayabileceği,
sade Türkçe ile 4-6 cümlelik bir özet yorum yaz. Teknik jargon kullanma.
Sonunda tek cümleyle "Şu an ne yapmalı?" önerisi ver.

- Bitcoin Fiyatı: ${btc_fiyat_r:,.0f}
- Mevcut Piyasa Rejimi: {rejim_etiketi}
- Kısa Vade (SMA10): {'Boğa' if kisa_bull else 'Ayı'}
- Uzun Vade (SMA50): {'Boğa' if makro_bull else 'Ayı'}
- 8 Yıllık Strateji Kazancı: %{kazanc:+.1f} (${strateji_deger:,.0f})

Sadece yorum metni üret.
"""
    return gemini_api(prompt)

def format_pct(x):
    return f"%{x:+.1f}"

def compute_trade_log(df):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d = d.dropna().copy()

    prev_regime = None
    prev_btc = 0.0
    prev_alt = 0.0
    cash = 10000.0
    btc_qty = 0.0
    alt_qty = 0.0
    rows = []

    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        fbtc, falt = row["Bitcoin"], row["Altin"]

        if r < s10 and r < s50:
            regime = "Güçlü Boğa"
            btc_pct, alt_pct = 100, 0
        elif r < s50 and r >= s10:
            regime = "Boğa + Düzeltme"
            btc_pct, alt_pct = 50, 50
        else:
            regime = "Altın Ağırlık"
            btc_pct, alt_pct = 0, 100

        portfolio_before = cash + btc_qty * fbtc + alt_qty * falt

        if prev_regime is None:
            action = "İlk Pozisyon"
        elif regime != prev_regime:
            action = f"{prev_regime} → {regime}"
        else:
            action = None

        if prev_regime is None or regime != prev_regime:
            if regime == "Güçlü Boğa":
                btc_qty = portfolio_before / fbtc
                alt_qty = 0.0
                cash = 0.0
            elif regime == "Boğa + Düzeltme":
                btc_qty = (portfolio_before * 0.5) / fbtc
                alt_qty = (portfolio_before * 0.5) / falt
                cash = 0.0
            else:
                btc_qty = 0.0
                alt_qty = portfolio_before / falt
                cash = 0.0

            portfolio_after = btc_qty * fbtc + alt_qty * falt + cash
            rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Eski_Rejim": prev_regime or "Yok",
                "Yeni_Rejim": regime,
                "Islem": action,
                "BTC_Pct": btc_pct,
                "Altin_Pct": alt_pct,
                "Portfoy": round(portfolio_after, 2),
                "Not": "Rejim değişimi"
            })
            prev_regime = regime
        else:
            continue

    log_df = pd.DataFrame(rows)
    if not log_df.empty:
        log_df["Getiri_%"] = log_df["Portfoy"].pct_change().fillna(0) * 100
    return d, log_df

def append_live_log(row):
    cols = ["Tarih", "Eski_Rejim", "Yeni_Rejim", "Islem", "BTC_Pct", "Altin_Pct", "Portfoy", "Not"]
    new_df = pd.DataFrame([row], columns=cols)
    if ROTATION_LOG_FILE.exists():
        old = pd.read_csv(ROTATION_LOG_FILE)
        all_df = pd.concat([old, new_df], ignore_index=True)
    else:
        all_df = new_df
    all_df.to_csv(ROTATION_LOG_FILE, index=False)

try:
    raw = verileri_getir()
    if raw.empty or len(raw) < 60:
        st.error("Veri havuzu henüz yeterli büyüklükte değil.")
        st.stop()

    data, trade_log = compute_trade_log(raw)
    if trade_log.empty:
        st.error("İşlem günlüğü üretilemedi.")
        st.stop()

    son = data.iloc[-1]
    btc_fiyat = son["Bitcoin"]
    altin_fiyat = son["Altin"]
    bakir_fiyat = son["Bakir"]
    son_rasyo = son["Rasyo"]
    sma10 = son["SMA10"]
    sma50 = son["SMA50"]

    makro_bull = son_rasyo < sma50
    kisa_bull = son_rasyo < sma10

    if makro_bull and kisa_bull:
        rejim_kodu = "strong_on"
        rejim_etiketi = "🟢🟢 GÜÇLÜ BOĞA"
        rejim_aciklama = "Her iki sinyal de BTC lehine · En güçlü alım bölgesi"
        status_text = "Güçlü Boğa"
        current_btc_pct, current_alt_pct = 100, 0
    elif makro_bull and not kisa_bull:
        rejim_kodu = "weak_on"
        rejim_etiketi = "🟡🟢 BOĞA + Kısa Düzeltme"
        rejim_aciklama = "Büyük trend yukarı · Kısa vadede hafif baskı"
        status_text = "Boğa + Düzeltme"
        current_btc_pct, current_alt_pct = 50, 50
    elif not makro_bull and kisa_bull:
        rejim_kodu = "weak_off"
        rejim_etiketi = "🟠🔴 AYI + Kısa Toparlanma"
        rejim_aciklama = "Büyük trend aşağı · Kısa vadede geçici rahatlama"
        status_text = "Ayı + Toparlanma"
        current_btc_pct, current_alt_pct = 0, 100
    else:
        rejim_kodu = "strong_off"
        rejim_etiketi = "🔴🔴 GÜÇLÜ AYI"
        rejim_aciklama = "Her iki sinyal de BTC aleyhine · En güçlü kaçış bölgesi"
        status_text = "Güçlü Ayı"
        current_btc_pct, current_alt_pct = 0, 100

    first_price = data["Bitcoin"].iloc[0]
    bh_qty = 10000.0 / first_price
    data["BuyHold"] = bh_qty * data["Bitcoin"]
    bh_son = data["BuyHold"].iloc[-1]
    bh_kazanc = (bh_son - 10000.0) / 10000.0 * 100

    rot_son = trade_log["Portfoy"].iloc[-1]
    rot_kazanc = (rot_son - 10000.0) / 10000.0 * 100

    state = load_state()
    prev_regime = state.get("last_regime")
    prev_daily = state.get("last_daily_date")
    today_str = date.today().isoformat()

    if prev_regime != status_text:
        if prev_regime is not None:
            live_row = {
                "Tarih": now_iso(),
                "Eski_Rejim": prev_regime,
                "Yeni_Rejim": status_text,
                "Islem": f"{prev_regime} → {status_text}",
                "BTC_Pct": current_btc_pct,
                "Altin_Pct": current_alt_pct,
                "Portfoy": round(rot_son, 2),
                "Not": "Canlı rejim değişimi"
            }
            append_live_log(live_row)

            if TOKEN and CHAT_ID:
                msg = (
                    f"◆ *LİKİDİTE REJİM DEĞİŞİMİ* ◆\n\n"
                    f"🪙 BTC: ${btc_fiyat:,.0f}\n"
                    f"📊 Yeni Rejim: {status_text}\n"
                    f"💼 Rotasyon: ${rot_son:,.0f} (%{rot_kazanc:+.1f})\n"
                    f"📌 Dağılım: BTC %{current_btc_pct:.0f} · Altın %{current_alt_pct:.0f}"
                )
                telegram_gonder(msg)

        state["last_regime"] = status_text

    if prev_daily != today_str:
        if TOKEN and CHAT_ID:
            daily_msg = (
                f"◆ *GÜNLÜK LİKİDİTE ÖZETİ* ◆\n\n"
                f"🪙 BTC: ${btc_fiyat:,.0f}\n"
                f"🥇 Altın: ${altin_fiyat:,.0f}\n"
                f"🥈 Bakır: ${bakir_fiyat:,.0f}\n"
                f"📊 Rejim: {status_text}\n"
                f"💼 Rotasyon: ${rot_son:,.0f} (%{rot_kazanc:+.1f})"
            )
            telegram_gonder(daily_msg)
        state["last_daily_date"] = today_str

    state["last_seen"] = now_iso()
    save_state(state)

    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
    c1.metric("Bitcoin Fiyatı", f"${btc_fiyat:,.0f}", f"{format_pct((btc_fiyat / data['Bitcoin'].iloc[-2] - 1) * 100)} son gün")
    c2.metric("Altın Fiyatı", f"${altin_fiyat:,.0f}", f"{format_pct((altin_fiyat / data['Altin'].iloc[-2] - 1) * 100)} son gün")
    c3.metric("8Y Rotasyon", f"${rot_son:,.0f}", f"{format_pct(rot_kazanc)}")
    c4.metric("BTC Al-Tut", f"${bh_son:,.0f}", f"{format_pct(bh_kazanc)}")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown(f"""
<div class="lk-regime lk-regime-{rejim_kodu.replace('_','-')}">
    <span>{rejim_etiketi}</span>
    <span style="font-weight:400; font-size:12px; color:#7C8595">{rejim_aciklama}</span>
    <span style="margin-left:auto; font-size:13px; color:#E6E9EF;">
        Şu an: <b style="color:#F0B90B">BTC %{current_btc_pct:.0f}</b>
        &nbsp;·&nbsp;
        <b style="color:#E5C07B">Altın %{current_alt_pct:.0f}</b>
    </span>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if rot_son > bh_son:
        st.success(f"✅ Rotasyon stratejisi al-tutun **${rot_son - bh_son:,.0f}** önünde")
    else:
        st.warning(f"Rotasyon stratejisi al-tuta kıyasla **${bh_son - rot_son:,.0f}** geride")

    st.markdown('<div class="lk-section">Likidite Rasyosu · SMA10 · SMA50 · BTC Fiyatı</div>', unsafe_allow_html=True)
    left, right = st.columns([1.7, 0.9], gap="large")

    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Süper Rasyo", line=dict(color="#7C8595", width=1.0), opacity=0.75))
        fig.add_trace(go.Scatter(x=data.index, y=data["SMA10"], name="SMA10", line=dict(color="#4ADE80" if kisa_bull else "#F87171", width=2, dash="dot")))
        fig.add_trace(go.Scatter(x=data.index, y=data["SMA50"], name="SMA50", line=dict(color="#4ADE80" if makro_bull else "#F87171", width=3)))
        fig.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC Fiyatı", line=dict(color="#F0B90B", width=1.2, dash="dot"), yaxis="y2"))
        fig.update_layout(
            height=560,
            template="plotly_dark",
            paper_bgcolor="#0F131C",
            plot_bgcolor="#0F131C",
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor="#1E2430"),
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
            "Değer": [status_text, f"{sma10:.4e}", f"{sma50:.4e}", f"{son_rasyo:.4e}", f"%{current_btc_pct:.0f}", f"%{current_alt_pct:.0f}"]
        })
        st.dataframe(ozet_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="lk-card">', unsafe_allow_html=True)
        st.markdown("**Son 10 İşlem**")
        st.dataframe(trade_log.tail(10), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="lk-section">Rotasyon Stratejisi vs BTC Al-Tut · Kısa Kıyas</div>', unsafe_allow_html=True)
    left2, right2 = st.columns([1.55, 1], gap="large")

    with left2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Rasyo", line=dict(color="#6FE3B5", width=1.6)))
        fig2.add_trace(go.Scatter(x=data.index, y=data["SMA10"], name="SMA10", line=dict(color="#F0B90B", width=1.2, dash="dot")))
        fig2.update_layout(
            height=300,
            template="plotly_dark",
            paper_bgcolor="#0F131C",
            plot_bgcolor="#0F131C",
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor="#1E2430"),
            yaxis=dict(title="Rasyo", gridcolor="#1E2430"),
            legend=dict(orientation="h", y=1.03, x=1, xanchor="right", bgcolor='rgba(0,0,0,0)')
        )
        st.plotly_chart(fig2, use_container_width=True)

    with right2:
        st.markdown('<div class="lk-card">', unsafe_allow_html=True)
        portfoy_df = pd.DataFrame({
            "Karşılaştırma": ["Rotasyon Son", "Al-Tut Son", "Fark", "Rotasyon Getiri"],
            "Değer": [f"${rot_son:,.0f}", f"${bh_son:,.0f}", f"${rot_son - bh_son:,.0f}", f"%{rot_kazanc:+.1f}"]
        })
        st.markdown("**Portföy Özeti**")
        st.dataframe(portfoy_df, use_container_width=True, hide_index=True)
        st.markdown("<div class='small-note'>BTC al-tut artık kısa referans olarak tutuluyor.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="lk-section">Portföy Dağılımı · BTC vs Altın Ağırlığı (%)</div>', unsafe_allow_html=True)
    left3, right3 = st.columns([1.35, 1], gap="large")

    with left3:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=data.index, y=data["BTC_Pct"], name="BTC Ağırlığı %", line=dict(color="#F0B90B", width=1.5), fill="tozeroy", fillcolor="rgba(240,185,11,0.15)"))
        fig3.add_trace(go.Scatter(x=data.index, y=data["Altin_Pct"], name="Altın Ağırlığı %", line=dict(color="#E5C07B", width=1.5), fill="tozeroy", fillcolor="rgba(229,192,123,0.10)"))
        fig3.update_layout(
            height=260,
            template="plotly_dark",
            paper_bgcolor="#0F131C",
            plot_bgcolor="#0F131C",
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor="#1E2430"),
            yaxis=dict(title="%", gridcolor="#1E2430", range=[0, 110]),
            legend=dict(orientation="h", y=1.08, x=1, xanchor="right", bgcolor='rgba(0,0,0,0)')
        )
        st.plotly_chart(fig3, use_container_width=True)

    with right3:
        st.markdown('<div class="lk-card">', unsafe_allow_html=True)
        dagilim_df = pd.DataFrame({
            "Alan": ["Şu An BTC", "Şu An Altın", "Kısa Vade", "Uzun Vade"],
            "Değer": [f"%{current_btc_pct:.0f}", f"%{current_alt_pct:.0f}", "Boğa" if kisa_bull else "Ayı", "Boğa" if makro_bull else "Ayı"]
        })
        st.markdown("**Dağılım ve Sinyal**")
        st.dataframe(dagilim_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="lk-section">Yapay Zeka Piyasa Yorumu</div>', unsafe_allow_html=True)
    yorum = None
    if GEMINI_KEY:
        with st.spinner("Piyasa verileri yorumlanıyor..."):
            yorum = gemini_yorum_cache(
                round(btc_fiyat / 500) * 500,
                status_text,
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
        st.info("AI yorumu şu an alınamadı. Veriler ve rotasyon tabloları normal çalışıyor.")

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    user_soru = st.text_input("Soru sor", label_visibility="collapsed", placeholder="Aklınıza takılan bir şey mi var? Buraya yazın...")
    if user_soru and GEMINI_KEY:
        with st.spinner("Yanıt hazırlanıyor..."):
            baglam = f"""
Sen bir piyasa analisti danışmanısın. Şu anki durum:
- BTC: ${btc_fiyat:,.0f}
- Rejim: {status_text}
- Kısa vade (SMA10): {'Boğa' if kisa_bull else 'Ayı'}
- Uzun vade (SMA50): {'Boğa' if makro_bull else 'Ayı'}
- 8Y Rotasyon: %{rot_kazanc:+.1f}

Sıradan bir yatırımcıya sade Türkçe ile, kısa ve net yanıt ver.
Kullanıcı sorusu: {user_soru}
"""
            yanit = gemini_api(baglam)
            if yanit:
                st.markdown(f'<div class="lk-ai-box">{yanit}</div>', unsafe_allow_html=True)
            else:
                st.info("Bu anda AI yanıtı alınamadı; lütfen tekrar deneyin.")

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="lk-section">8 Yıllık Tüm Rotasyon İşlemleri</div>', unsafe_allow_html=True)
    st.dataframe(trade_log, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Genel hata: {e}")
