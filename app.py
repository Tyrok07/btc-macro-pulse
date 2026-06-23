import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── SAYFA AYARI ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

if "GEMINI_API_KEY" not in st.secrets:
    st.secrets["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
if "TELEGRAM_TOKEN" not in st.secrets:
    st.secrets["TELEGRAM_TOKEN"] = os.getenv("TELEGRAM_TOKEN", "")
if "TELEGRAM_CHAT_ID" not in st.secrets:
    st.secrets["TELEGRAM_CHAT_ID"] = os.getenv("TELEGRAM_CHAT_ID", "")

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    SCHEDULER_OK = True
except ImportError:
    SCHEDULER_OK = False

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&family=JetBrains+Mono:wght=400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #F8FAFC; color: #1E293B; }
.lk-header { padding: 26px 4px 18px 4px; border-bottom: 1px solid #E2E8F0; margin-bottom: 22px; }
.lk-eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #0EA5E9; margin-bottom: 6px; }
.lk-title { font-size: 30px; font-weight: 700; color: #0F172A; margin: 0; letter-spacing: -0.01em; }
.lk-subtitle { font-size: 14px; color: #64748B; margin-top: 5px; }
div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05); }
div[data-testid="stMetric"] label { color: #64748B !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.04em; }
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-size: 20px !important; color: #0F172A !important; }
.lk-regime { border-radius: 12px; padding: 13px 18px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; line-height: 1.6; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.lk-regime-strong-on { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.3); color: #166534; }
.lk-regime-weak-on { background: rgba(234,179,8,0.08); border-color: rgba(234,179,8,0.3); color: #854D0E; }
.lk-regime-weak-off { background: rgba(249,115,22,0.08); border-color: rgba(249,115,22,0.3); color: #9A3412; }
.lk-regime-strong-off { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.3); color: #991B1B; }
.lk-section { font-size: 15px; font-weight: 600; color: #0F172A; margin: 28px 0 12px 0; padding-left: 10px; border-left: 3px solid #0EA5E9; }
.lk-ai-box { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px 24px; line-height: 1.80; font-size: 15px; color: #334155; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05); }
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">Sabit İkili (BTC + XAU) + Dinamik Üçüncü Katman</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Sabit Omurga Modeli: Bitcoin ve Altın Çekirdeği Korunarak Fon/Nakit Katmanının Entegrasyonu</p>
</div>
""", unsafe_allow_html=True)

GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()

# YENİ REJİM DAĞILIMI (BTC VE ALTIN SABİT KALACAK ŞEKİLDE DÜZENLENDİ)
def rejim_tespit_sabit_ikili(r, s10, s50):
    if r < s10 and r < s50:
        return ("Güçlü Boğa", 80, 20, 0, "strong-on", "🟢 GÜÇLÜ BOĞA", "Ana Omurga BTC Ağırlıklı · %80 BTC · %20 Altın")
    elif r < s50:
        return ("Boğa + Düzeltme", 50, 50, 0, "weak-on", "🟡 BOĞA + Düzeltme", "Sabit İkili Yarı Yarıya Dengede · %50 BTC · %50 Altın")
    elif r < s10:
        return ("Ayı + Toparlanma", 30, 50, 20, "weak-off", "🟠 AYI + Toparlanma", "Omurga Korunuyor + %20 Savunma Sanayii (ITA) / Nakit")
    else:
        return ("Güçlü Ayı", 10, 60, 30, "strong-off", "🔴 GÜÇLÜ AYI", "Maksimum Defans Modu · %10 BTC · %60 Altın · %30 Savunma / Nakit")

def fmt_pct(x): return f"%{x:+.1f}"
def fmt_usd(x): return f"${x:,.0f}"

@st.cache_data(ttl=1800)
def fear_and_greed_getir():
    try:
        res = requests.get("https://api.alternative.me/fng/", timeout=10)
        if res.ok:
            data = res.json().get("data", [{}])[0]
            return int(data.get("value", 50)), data.get("value_classification", "Neutral")
    except Exception: pass
    return 50, "Neutral"

@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin", "DX-Y.NYB": "DXY", "^TNX": "US10Y", "ITA": "Savunma"}
    df = yf.download(list(symbols.keys()), period="8y", interval="1d", auto_adjust=False, multi_level_index=False, progress=False)
    if df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df = df["Close"].copy() if "Close" in df.columns.get_level_values(0) else df.set_axis(df.columns.get_level_values(0), axis=1)
    elif "Close" in df.columns:
        df = df["Close"]
    df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
    return df[["Altin", "Bakir", "Bitcoin", "DXY", "US10Y", "Savunma"]].ffill().bfill()

# ── SABİT İKİLİ ODAKLI BACKTEST MOTORU ─────────────────────────────────────────
def backtest_sabit_ikili(df):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d = d.dropna().copy()
    
    cash = 10000.0
    btc_qty = alt_qty = sav_qty = 0.0
    prev_regime = None
    trade_rows, equity = [], []
    btc_gun = alt_gun = sav_gun = 0
    max_port = 10000.0
    max_dd = 0.0
    
    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        bp, ap, sp = float(row["Bitcoin"]), float(row["Altin"]), float(row["Savunma"])
        isim, t_btc, t_alt, t_sav, _, etiket, _ = rejim_tespit_sabit_ikili(r, s10, s50)
        
        port_val = (btc_qty * bp) + (alt_qty * ap) + (sav_qty * sp)
        if prev_regime is None: port_val = cash
            
        if (prev_regime is None) or (isim != prev_regime):
            btc_qty = (port_val * (t_btc / 100.0)) / bp if t_btc > 0 else 0.0
            alt_qty = (port_val * (t_alt / 100.0)) / ap if t_alt > 0 else 0.0
            sav_qty = (port_val * (t_sav / 100.0)) / sp if t_sav > 0 else 0.0
            
            port_after = (btc_qty * bp) + (alt_qty * ap) + (sav_qty * sp)
            trade_rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'Başlangıç'} → {isim}",
                "Rejim": etiket, 
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt} · Fon %{t_sav}",
                "Portföy": round(port_after, 0), 
            })
            prev_regime = isim
            
        port_now = (btc_qty * bp) + (alt_qty * ap) + (sav_qty * sp)
        max_port = max(max_port, port_now)
        dd = (port_now - max_port) / max_port * 100
        max_dd = min(max_dd, dd)
        
        if t_btc > 0: btc_gun += 1
        if t_alt > 0: alt_gun += 1
        if t_sav > 0: sav_gun += 1
        equity.append(port_now)
        
    d["Portfoy"] = equity
    stats = {"btc_gun": btc_gun, "alt_gun": alt_gun, "sav_gun": sav_gun, "max_dd": round(max_dd, 1)}
    return d, pd.DataFrame(trade_rows), stats

# ── YAPAY ZEKA MOTORU ─────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def gemini_yorum_sabit_omurga(rejim_adi, btc, alt, sav, dxy, us10y, fng_val, fng_class, dagilim_info):
    if not GEMINI_KEY: return "Gemini API Anahtarı eksik."
    prompt = (
        f"Sen deneyimli bir fon yöneticisisin. Portföy stratejimiz 'Sabit İkili Omurga' mantığına dayanıyor.\n"
        f"Yani Bitcoin ve Altın'ı asla tamamen sıfırlamıyoruz, piyasa çökse de bu ikili ana çekirdeği oluşturuyor.\n"
        f"Üçüncü katman olan Savunma Sanayii Fonu (ITA) / Nakit ise sadece ayı dönemlerinde dengeleyici joker eleman olarak giriyor.\n\n"
        f"ANLIK VERİLER:\n"
        f"- Rejim Durumu: {rejim_adi} -> {dagilim_info}\n"
        f"- BTC: {fmt_usd(btc)} · Altın: {fmt_usd(alt)} · Üçüncü Katman (ITA): ${sav:.2f}\n"
        f"- Makro: DXY: {dxy:.2f} · US10Y Faiz: %{us10y:.2f} · Fear & Greed: {fng_val}/100 ({fng_class})\n\n"
        f"Bu stratejik felsefeyi yansıtan, Bitcoin ve Altın omurgasının neden sabit kalması gerektiğini açıklayan kurumsal ve net 4 cümlelik bir analiz yaz."
    )
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text if response.text else "Yorum üretilemedi."
    except Exception as e: return f"AI Bağlantı Hatası: {e}"

# ── EKRAN ÇIKTILARI ───────────────────────────────────────────────────────────
try:
    raw = verileri_getir()
    data, trade_log, stats = backtest_sabit_ikili(raw)
    last = data.iloc[-1]
    
    btc_fiyat, alt_fiyat, sav_fiyat = float(last["Bitcoin"]), float(last["Altin"]), float(last["Savunma"])
    dxy_deger, us10y_deger = float(last["DXY"]), float(last["US10Y"])
    son_rasyo = float(last["Rasyo"])
    sma10, sma50 = float(last["SMA10"]), float(last["SMA50"])
    
    fng_val, fng_class = fear_and_greed_getir()
    isim_now, btc_pct_now, alt_pct_now, sav_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit_sabit_ikili(son_rasyo, sma10, sma50)
    dagilim_metni = f"BTC %{btc_pct_now} · Altın %{alt_pct_now} · Üçüncü Katman %{sav_pct_now}"
    
    rot_son = float(data["Portfoy"].iloc[-1])
    rot_kazanc = (rot_son / 10000.0 - 1) * 100

    # Metrikler
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin", fmt_usd(btc_fiyat))
    c2.metric("Altın", fmt_usd(alt_fiyat))
    c3.metric("Üçüncü Katman (ITA)", f"${sav_fiyat:.2f}")
    c4.metric("DXY / US10Y Faiz", f"{dxy_deger:.2f} / %{us10y_deger:.2f}")
    c5.metric("Psychology (F&G)", f"{fng_val}/100", fng_class)
    
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    
    # Rejim Banner
    st.markdown(f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
        <span>{rejim_etiketi}</span>
        <span style="font-weight:400; font-size:12px; color:#64748B">{rejim_aciklama}</span>
        <span style="margin-left:auto; font-size:13px;">
            Aktif Taktik: <b style="color:#B45309">BTC %{btc_pct_now}</b> · <b style="color:#0369A1">Altın %{alt_pct_now}</b> · <b style="color:#0EA5E9">Dinamik Katman %{sav_pct_now}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    # Performans
    st.markdown('<div class="lk-section">Strateji Performans İstatistikleri (Sabit Omurga Modeli)</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("8Y Sabit Omurga Sermaye", fmt_usd(rot_son), fmt_pct(rot_kazanc))
    s2.metric("Maks. Drawdown", fmt_pct(stats["max_dd"]))
    s3.metric("BTC Pozisyonlu Gün", f"{stats['btc_gun']} gün")
    s4.metric("Altın Pozisyonlu Gün", f"{stats['alt_gun']} gün")
    s5.metric("Üçüncü Katman Aktif Gün", f"{stats['sav_gun']} gün")

    # Yapay Zeka
    st.markdown('<div class="lk-section">✨ Çok Katmanlı Yapay Zeka Stratejik Sabit Çekirdek Analizi</div>', unsafe_allow_html=True)
    ai_yorum = gemini_yorum_sabit_omurga(isim_now, btc_fiyat, alt_fiyat, sav_fiyat, dxy_deger, us10y_deger, fng_val, fng_class, dagilim_metni)
    st.markdown(f'<div class="lk-ai-box">{ai_yorum}</div>', unsafe_allow_html=True)

    # Grafik
    st.markdown('<div class="lk-section">Sabit Omurga Sermaye Eğrisi</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="Sabit Omurga Modeli", line=dict(color="#0EA5E9", width=2.5)))
    fig.update_layout(height=350, template="plotly_white", paper_bgcolor="#F8FAFC", plot_bgcolor="#FFFFFF", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Hata: {e}")
