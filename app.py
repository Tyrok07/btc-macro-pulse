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
ROTATION_LOG_FILE = STATE_DIR / "rotasyon_log_live.csv"
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0B0E14; color: #E6E9EF; }
.lk-shell { max-width: 1600px; margin: 0 auto; }
.lk-header { padding: 26px 8px 18px 8px; border-bottom: 1px solid #1E2430; margin-bottom: 22px; }
.lk-eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: #6FE3B5; margin-bottom: 6px; }
.lk-title { font-size: 32px; font-weight: 700; color: #F2F4F8; margin: 0; letter-spacing: -0.01em; }
.lk-subtitle { font-size: 14px; color: #7C8595; margin-top: 6px; }
div[data-testid="stMetric"] { background: #131722; border: 1px solid #1E2430; border-radius: 12px; padding: 14px 16px; }
div[data-testid="stMetric"] label { color: #7C8595 !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.04em; }
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-size: 20px !important; color: #F2F4F8 !important; }
.lk-regime { border-radius: 14px; padding: 14px 16px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; line-height: 1.6; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.lk-regime-strong-on  { background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.5);  color: #4ADE80; }
.lk-regime-weak-on    { background: rgba(234,179,8,0.10);  border-color: rgba(234,179,8,0.4);  color: #FCD34D; }
.lk-regime-weak-off   { background: rgba(249,115,22,0.10); border-color: rgba(249,115,22,0.4); color: #FB923C; }
.lk-regime-strong-off { background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.4); color: #F87171; }
.lk-section { font-size: 15px; font-weight: 600; color: #F2F4F8; margin: 22px 0 12px 0; padding-left: 10px; border-left: 3px solid #6FE3B5; }
.lk-card { background: #0F131C; border: 1px solid #1E2430; border-radius: 16px; padding: 16px 16px 12px 16px; }
.lk-ai-box { background: #131722; border: 1px solid #1E2430; border-radius: 12px; padding: 20px 22px; line-height: 1.75; font-size: 15px; color: #C8CDD8; }
.small-note { color: #7C8595; font-size: 12px; }
.stButton > button { background: #131722; border: 1px solid #2A3140; color: #E6E9EF; border-radius: 8px; font-weight: 500; padding: 8px 18px; }
.stTextInput input { background: #131722; border: 1px solid #1E2430; color: #E6E9EF; border-radius: 8px; }
[data-testid="stDataFrame"] { border: 1px solid #1E2430; border-radius: 12px; overflow: hidden; }
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
    df = yf.download(list(semboller.keys()), period="8y", interval="1d", auto_adjust=False, group_by="column", multi_level_index=False, progress=False)
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
    close_df = close_df.rename(columns={c: semboller[c] for c in close_df.columns if c in semboller})
    return close_df[["Altin", "Bakir", "Bitcoin"]].ffill().bfill()

def gemini_api(prompt):
    if not GEMINI_KEY:
        return None
    models = ["gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-2.0-flash"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
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

def backtest_trades(df):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d = d.dropna().copy()

    cash = 10000.0
    btc_qty = 0.0
    alt_qty = 0.0
    prev_regime = None
    rows = []
    equity_curve = []

    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        btc_px, alt_px = row["Bitcoin"], row["Altin"]

        if r < s10 and r < s50:
            regime = "Güçlü Boğa"
            target_btc, target_alt = 100, 0
        elif r < s50 and r >= s10:
            regime = "Boğa + Düzeltme"
            target_btc, target_alt = 50, 50
        else:
            regime = "Altın Ağırlık"
            target_btc, target_alt = 0, 100

        port_before = cash + btc_qty * btc_px + alt_qty * alt_px
        changed = (prev_regime is None) or (regime != prev_regime)

        if changed:
            if regime == "Güçlü Boğa":
                btc_qty = port_before / btc_px
                alt_qty = 0.0
                cash = 0.0
            elif regime == "Boğa + Düzeltme":
                btc_qty = (port_before * 0.5) / btc_px
                alt_qty = (port_before * 0.5) / alt_px
                cash = 0.0
            else:
                btc_qty = 0.0
                alt_qty = port_before / alt_px
                cash = 0.0

            port_after = cash + btc_qty * btc_px + alt_qty * alt_px
            rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Eski_Rejim": prev_regime or "Yok",
                "Yeni_Rejim": regime,
                "Islem": f"{prev_regime or 'Yok'} → {regime}",
                "BTC_Pct": target_btc,
                "Altin_Pct": target_alt,
                "Portfoy_Oncesi": round(port_before, 2),
                "Portfoy_Sonrasi": round(port_after, 2),
                "Günlük_Portfoy": round(port_after, 2),
                "Kümülatif_Getiri_%": round((port_after / 10000.0 - 1) * 100, 2),
                "Not": "Rejim değişimi"
            })
            prev_regime = regime

        equity_curve.append({
            "Tarih": idx,
            "Portfoy": cash + btc_qty * btc_px + alt_qty * alt_px
        })

    trade_log = pd.DataFrame(rows)
    equity_df = pd.DataFrame(equity_curve).set_index("Tarih")
    if not trade_log.empty:
        trade_log["Önceki_Satır_Getiri_%"] = trade_log["Portfoy_Sonrasi"].pct_change().fillna(0) * 100
    return d, trade_log, equity_df

try:
    raw = verileri_getir()
    if raw.empty or len(raw) < 60:
        st.error("Veri havuzu henüz yeterli büyüklükte değil.")
        st.stop()

    data, trade_log, equity_df = backtest_trades(raw)
    if trade_log.empty:
        st.error("İşlem günlüğü üretilemedi.")
        st.stop()

    last = data.iloc[-1]
    btc_fiyat = last["Bitcoin"]
    altin_fiyat = last["Altin"]
    bakir_fiyat = last["Bakir"]
    son_rasyo = last["Rasyo"]
    sma10 = last["SMA10"]
    sma50 = last["SMA50"]

    kisa_bull = son_rasyo < sma10
    makro_bull = son_rasyo < sma50

    if makro_bull and kisa_bull:
        rejim_kodu = "strong_on"; rejim_etiketi = "🟢🟢 GÜÇLÜ BOĞA"; rejim_aciklama = "Her iki sinyal BTC lehine"; status_text = "Güçlü Boğa"; btc_pct_now, alt_pct_now = 100, 0
    elif makro_bull and not kisa_bull:
        rejim_kodu = "weak_on"; rejim_etiketi = "🟡🟢 BOĞA + Kısa Düzeltme"; rejim_aciklama = "Büyük trend yukarı"; status_text = "Boğa + Düzeltme"; btc_pct_now, alt_pct_now = 50, 50
    elif not makro_bull and kisa_bull:
        rejim_kodu = "weak_off"; rejim_etiketi = "🟠🔴 AYI + Kısa Toparlanma"; rejim_aciklama = "Büyük trend aşağı"; status_text = "Ayı + Toparlanma"; btc_pct_now, alt_pct_now = 0, 100
    else:
        rejim_kodu = "strong_off"; rejim_etiketi = "🔴🔴 GÜÇLÜ AYI"; rejim_aciklama = "Her iki sinyal BTC aleyhine"; status_text = "Güçlü Ayı"; btc_pct_now, alt_pct_now = 0, 100

    first_btc = data["Bitcoin"].iloc[0]
    bh_qty = 10000.0 / first_btc
    data["BuyHold"] = bh_qty * data["Bitcoin"]
    bh_son = data["BuyHold"].iloc[-1]
    bh_kazanc = (bh_son / 10000.0 - 1) * 100

    rot_son = equity_df["Portfoy"].iloc[-1]
    rot_kazanc = (rot_son / 10000.0 - 1) * 100

    st.title("Likidite Kompozit Paneli")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bitcoin", f"${btc_fiyat:,.0f}", f"{format_pct((btc_fiyat / data['Bitcoin'].iloc[-2] - 1) * 100)} son gün")
    c2.metric("Altın", f"${altin_fiyat:,.0f}", f"{format_pct((altin_fiyat / data['Altin'].iloc[-2] - 1) * 100)} son gün")
    c3.metric("8Y Rotasyon", f"${rot_son:,.0f}", f"{format_pct(rot_kazanc)}")
    c4.metric("BTC Al-Tut", f"${bh_son:,.0f}", f"{format_pct(bh_kazanc)}")

    st.markdown(f"**Güncel Rejim:** {rejim_etiketi} · {rejim_aciklama}")

    st.markdown("## Likidite Rasyosu")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Rasyo", line=dict(color="#7C8595", width=1.2)))
    fig1.add_trace(go.Scatter(x=data.index, y=data["SMA10"], name="SMA10", line=dict(color="#4ADE80" if kisa_bull else "#F87171", width=2, dash="dot")))
    fig1.add_trace(go.Scatter(x=data.index, y=data["SMA50"], name="SMA50", line=dict(color="#4ADE80" if makro_bull else "#F87171", width=3)))
    fig1.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC", line=dict(color="#F0B90B", width=1.2, dash="dot"), yaxis="y2"))
    fig1.update_layout(height=520, template="plotly_dark", paper_bgcolor="#0F131C", plot_bgcolor="#0F131C", yaxis=dict(title="Rasyo"), yaxis2=dict(title="BTC", overlaying="y", side="right"))
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("## Güncel Özet")
    st.dataframe(pd.DataFrame({
        "Alan": ["Rejim", "SMA10", "SMA50", "Rasyo", "BTC %", "Altın %"],
        "Değer": [status_text, f"{sma10:.6e}", f"{sma50:.6e}", f"{son_rasyo:.6e}", f"%{btc_pct_now:.0f}", f"%{alt_pct_now:.0f}"]
    }), use_container_width=True, hide_index=True)

    st.markdown("## 8 Yıllık İşlem Günlüğü")
    st.dataframe(trade_log, use_container_width=True, hide_index=True)

    st.markdown("## Portföy Eğrisi")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=equity_df.index, y=equity_df["Portfoy"], name="Rotasyon Portföyü", line=dict(color="#6FE3B5", width=2.5)))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BuyHold"], name="BTC Al-Tut", line=dict(color="#F0B90B", width=1.3, dash="dot")))
    fig2.update_layout(height=320, template="plotly_dark", paper_bgcolor="#0F131C", plot_bgcolor="#0F131C", yaxis=dict(title="USD"))
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("## Yapay Zeka Piyasa Yorumu")
    yorum = None
    if GEMINI_KEY:
        with st.spinner("Piyasa verileri yorumlanıyor..."):
            yorum = gemini_yorum_cache(round(btc_fiyat / 500) * 500, status_text, rot_kazanc, bh_kazanc, rot_son, bh_son, kisa_bull, makro_bull)
    st.markdown(f'<div class="lk-ai-box">{yorum if yorum else "AI yorumu alınamadı. Veriler normal çalışıyor."}</div>', unsafe_allow_html=True)

    st.markdown("## Son Güncelleme")
    st.dataframe(pd.DataFrame({
        "Alan": ["BTC", "Altın", "Bakır", "Rotasyon", "BTC Al-Tut"],
        "Değer": [f"${btc_fiyat:,.0f}", f"${altin_fiyat:,.0f}", f"${bakir_fiyat:,.0f}", f"${rot_son:,.0f}", f"${bh_son:,.0f}"]
    }), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Genel hata: {e}")
