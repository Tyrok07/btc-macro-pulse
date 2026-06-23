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

# Yerel geliştirme ortamındaki .env dosyasını yükle
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

# ── AYDINLIK TEMA CSS ─────────────────────────────────────────────────────────
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
.stButton > button { background: #FFFFFF; border: 1px solid #CBD5E1; color: #334155; border-radius: 8px; font-weight: 500; padding: 8px 18px; }
.stButton > button:hover { border-color: #0EA5E9; color: #0EA5E9; }
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / XCUUSD / BTCUSD + ITA ETF · Savunma Sanayii Hedge Katmanı</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Adım 3 (Revize): Ayı Sezonlarında Parayı Nakit Yerine Küresel Savunma Sanayii Fonunda Büyütme Modeli</p>
</div>
""", unsafe_allow_html=True)

GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()

def rejim_tespit(r, s10, s50):
    if r < s10 and r < s50:
        return ("Güçlü Boğa", 100, 0, 0, "strong-on", "🟢 GÜÇLÜ BOĞA", "Her iki sinyal BTC lehine · Maksimum Risk On")
    elif r < s50:
        return ("Boğa + Düzeltme", 50, 50, 0, "weak-on", "🟡 BOĞA + Kısa Düzeltme", "Büyük trend yukarı · Dengeli Dağılım")
    elif r < s10:
        return ("Ayı + Toparlanma", 0, 50, 50, "weak-off", "🟠 AYI + Kısa Toparlanma", "Geçici rahatlama · %50 Savunma Sanayii (ITA) Kalkanı")
    else:
        return ("Güçlü Ayı", 0, 20, 80, "strong-off", "🔴 GÜÇLÜ AYI", "Sinyaller aleyhte · %80 Savunma Sanayii (ITA) Maksimum Hedge")

def fmt_pct(x): return f"%{x:+.1f}"
def fmt_usd(x): return f"${x:,.0f}"

def load_state():
    try: return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8")) if ALERT_STATE_FILE.exists() else {}
    except Exception: return {}

def save_state(s):
    try: ALERT_STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception: pass

def telegram_gonder(mesaj):
    if not TOKEN or not CHAT_ID: return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
        return r.ok
    except Exception: return False

@st.cache_data(ttl=1800)
def fear_and_greed_getir():
    try:
        res = requests.get("https://api.alternative.me/fng/", timeout=10)
        if res.ok:
            data = res.json().get("data", [{}])[0]
            return int(data.get("value", 50)), data.get("value_classification", "Neutral")
    except Exception: pass
    return 50, "Neutral"

# ── CANLI VERİ BESLEMESİ (ITA DAHİL EDİLDİ) ────────────────────────────────────
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
    cols = [c for c in ["Altin", "Bakir", "Bitcoin", "DXY", "US10Y", "Savunma"] if c in df.columns]
    return df[cols].ffill().bfill()

def günlük_rejim_kontrol_ve_bildir():
    try:
        symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin", "ITA": "Savunma"}
        df = yf.download(list(symbols.keys()), period="60d", interval="1d", auto_adjust=False, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df = df["Close"]
        df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
        df = df[["Altin","Bakir","Bitcoin", "Savunma"]].ffill().bfill().dropna()
        if len(df) < 52: return
        
        df["Rasyo"] = df["Altin"] / (df["Bakir"] * df["Bitcoin"])
        df["SMA10"] = df["Rasyo"].rolling(10).mean()
        df["SMA50"] = df["Rasyo"].rolling(50).mean()
        last = df.dropna().iloc[-1]
        
        isim, t_btc, t_alt, t_sav, _, etiket, _ = rejim_tespit(float(last["Rasyo"]), float(last["SMA10"]), float(last["SMA50"]))
        fng_val, fng_class = fear_and_greed_getir()
        state = load_state()
        bugun_str = datetime.now().strftime("%Y-%m-%d")
        
        if state.get("son_rapor_tarihi") != bugun_str:
            mesaj = (
                f"📊 *SAVUNMA SANAYİİ HEDGE RAPORU*\n\n"
                f"Durum: *{etiket}*\n"
                f"🧠 Korku & Açgözlülük: {fng_val}/100 ({fng_class})\n"
                f"🪙 BTC Fiyat: {fmt_usd(float(last['Bitcoin']))}\n"
                f"🚀 ITA Savunma Fiyat: ${float(last['Savunma']):.2f}\n"
                f"💼 Dağılım: BTC %{t_btc} · Altın %{t_alt} · Savunma %{t_sav}\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            if telegram_gonder(mesaj): state["son_rapor_tarihi"] = bugun_str
        
        state.update({"rejim": etiket, "son_kontrol": datetime.now().strftime("%d.%m.%Y %H:%M")})
        save_state(state)
    except Exception: pass

if SCHEDULER_OK and "scheduler_started" not in st.session_state:
    _sch = BackgroundScheduler(timezone="Europe/Istanbul")
    _sch.add_job(günlük_rejim_kontrol_ve_bildir, "cron", hour=10, minute=0, id="gunluk_kontrol", replace_existing=True)
    _sch.start()
    st.session_state["scheduler_started"] = True

# ── SAVUNMA SANAYİİ DESTEKLİ GELİŞMİŞ BACKTEST MOTORU ─────────────────────────
def backtest_aerospace_hedge(df):
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
        isim, t_btc, t_alt, t_sav, _, etiket, _ = rejim_tespit(r, s10, s50)
        
        port_val = (btc_qty * bp) + (alt_qty * ap) + (sav_qty * sp)
        if prev_regime is None: port_val = cash
            
        changed = (prev_regime is None) or (isim != prev_regime)
        if changed:
            btc_qty = (port_val * (t_btc / 100.0)) / bp if t_btc > 0 else 0.0
            alt_qty = (port_val * (t_alt / 100.0)) / ap if t_alt > 0 else 0.0
            sav_qty = (port_val * (t_sav / 100.0)) / sp if t_sav > 0 else 0.0
            
            port_after = (btc_qty * bp) + (alt_qty * ap) + (sav_qty * sp)
            trade_rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'Başlangıç'} → {isim}",
                "Rejim": etiket, 
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt} · Savunma %{t_sav}",
                "Portföy": round(port_after, 0), 
                "Getiri": round((port_after / 10000.0 - 1) * 100, 1),
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
    stats = {"islem_sayisi": len(trade_rows), "btc_gun": btc_gun, "alt_gun": alt_gun, "sav_gun": sav_gun, "max_dd": round(max_dd, 1), "toplam_gun": len(d)}
    return d, pd.DataFrame(trade_rows), stats

# ── SAVUNMA ODAKLI YAPAY ZEKA ANALİZ MOTORU ───────────────────────────────────
@st.cache_data(ttl=1800)
def gemini_api_yorum_uret_defense(rejim_adi, btc, alt, sav, dxy, us10y, fng_val, fng_class, rasyo, s10, s50, dagilim_info):
    if not GEMINI_KEY: return "Gemini API Anahtarı eksik."
    
    sapma_sma10 = ((rasyo / s10) - 1) * 100
    sapma_sma50 = ((rasyo / s50) - 1) * 100
    
    prompt = (
        f"Sen jeopolitik ve makro riskleri mükemmel yöneten kıdemli bir hedge fonu yöneticisisin.\n\n"
        f"Ayı piyasalarında parayı atıl nakitte bekletmek yerine, küresel risk zırhı olan ABD Savunma Sanayii ETF'inde (ITA) değerlendiriyoruz.\n\n"
        f"GÜNCEL TERMİNAL VERİLERİ:\n"
        f"- Sinyal Rejimi: {rejim_adi} -> {dagilim_info}\n"
        f"- Fiyatlar -> BTC: {fmt_usd(btc)} · Altın: {fmt_usd(alt)} · ITA Savunma ETF: ${sav:.2f}\n"
        f"- Makro Güçler -> DXY: {dxy:.2f} · US10Y Faiz: %{us10y:.2f}\n"
        f"- Psikoloji -> Fear & Greed: {fng_val}/100 ({fng_class})\n"
        f"- Likidite Rasyosu: {rasyo:.6f} (SMA10 Sapma: {sapma_sma10:+.2f}%, SMA50 Sapma: {sapma_sma50:+.2f}%)\n\n"
        f"ANALİZ KURALLARI:\n"
        f"1. İlk cümlede doğrudan anlık ITA Savunma ETF fiyatını, DXY ve faiz baskısını harmanlayarak küresel sermayenin savunma kalkanına olan ihtiyacını belirt.\n"
        f"2. Ayı rejiminde portföyün büyük kısmını Savunma Sanayii fonunda (ITA) hedge etmenin, atıl stablecoin'de (nakit) beklemeye kıyasla yaratacağı getiri (alfa) avantajını kurumsal bir dille anlat.\n"
        f"3. Kriptodaki korku endeksini ({fng_val}/100) yorumlayarak, savunma fonundan kriptoya geri dönülecek o stratejik dipten alım dönemini pusu mantığıyla açıkla.\n"
        f"4. Net, kurumsal ve en fazla 4-6 cümle olsun."
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_KEY)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            if response.text: return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return f"Yapay zeka yoğun (503). Hata: {e}"
    return "Yapay zeka motoruna erişilemiyor."

# ── ANA GÖRÜNÜM ───────────────────────────────────────────────────────────────
try:
    raw = verileri_getir()
    if raw.empty or len(raw) < 60:
        st.error("Veri yetersiz.")
        st.stop()
        
    data, trade_log, stats = backtest_aerospace_hedge(raw)
    last = data.iloc[-1]
    
    btc_fiyat = float(last["Bitcoin"])
    alt_fiyat = float(last["Altin"])
    sav_fiyat = float(last["Savunma"]) if "Savunma" in last else 120.0
    dxy_deger = float(last["DXY"]) if "DXY" in last else 100.0
    us10y_deger = float(last["US10Y"]) if "US10Y" in last else 4.0
    son_rasyo = float(last["Rasyo"])
    sma10, sma50 = float(last["SMA10"]), float(last["SMA50"])
    
    fng_val, fng_class = fear_and_greed_getir()
    isim_now, btc_pct_now, alt_pct_now, sav_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit(son_rasyo, sma10, sma50)
    dagilim_metni = f"BTC %{btc_pct_now} · Altın %{alt_pct_now} · Savunma %{sav_pct_now}"
    
    data["BH_BTC"] = (10000.0 / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
    data["BH_Altin"] = (10000.0 / float(data["Altin"].iloc[0])) * data["Altin"]
    rot_son = float(data["Portfoy"].iloc[-1])
    rot_kazanc = (rot_son / 10000.0 - 1) * 100

    # Metrikler
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin", fmt_usd(btc_fiyat))
    c2.metric("Altın", fmt_usd(alt_fiyat))
    c3.metric("ITA Savunma ETF", f"${sav_fiyat:.2f}")
    c4.metric("DXY / US10Y Faiz", f"{dxy_deger:.2f} / %{us10y_deger:.2f}")
    c5.metric("Psychology (F&G)", f"{fng_val}/100", fng_class)
    
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    
    # Rejim Banner
    st.markdown(f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
        <span>{rejim_etiketi}</span>
        <span style="font-weight:400; font-size:12px; color:#64748B">{rejim_aciklama}</span>
        <span style="margin-left:auto; font-size:13px;">
            Aktif Taktik: <b style="color:#B45309">BTC %{btc_pct_now}</b> · <b style="color:#0369A1">Altın %{alt_pct_now}</b> · <b style="color:#0EA5E9">Savunma (ITA) %{sav_pct_now}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    # Performans İstatistikleri
    st.markdown('<div class="lk-section">Strateji Performans İstatistikleri (Savunma Hedge Raporu)</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("8Y Savunma Hedge Sermaye", fmt_usd(rot_son), fmt_pct(rot_kazanc))
    s2.metric("Maks. Drawdown", fmt_pct(stats["max_dd"]))
    s3.metric("BTC'de Kalınan Gün", f"{stats['btc_gun']} gün")
    s4.metric("Altın'da Kalınan Gün", f"{stats['alt_gun']} gün")
    s5.metric("Savunma Sanayiinde Gün", f"{stats['sav_gun']} gün")

    # Grafik 1: Likidite
    st.markdown('<div class="lk-section">Likidite Rasyosu Durumu</div>', unsafe_allow_html=True)
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Rasyo", line=dict(color="#94A3B8", width=1.0)))
    fig1.update_layout(height=350, template="plotly_white", paper_bgcolor="#F8FAFC", plot_bgcolor="#FFFFFF", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig1, use_container_width=True)

    # Yapay Zeka Alanı
    st.markdown('<div class="lk-section">✨ Çok Katmanlı Yapay Zeka Stratejik Savunma Analizi</div>', unsafe_allow_html=True)
    ai_yorum = gemini_api_yorum_uret_defense(isim_now, btc_fiyat, alt_fiyat, sav_fiyat, dxy_deger, us10y_deger, fng_val, fng_class, son_rasyo, sma10, sma50, dagilim_metni)
    st.markdown(f'<div class="lk-ai-box">{ai_yorum}</div>', unsafe_allow_html=True)

    # Grafik 2: Portföy Karşılaştırma
    st.markdown('<div class="lk-section">Yeni Sermaye Eğrisi · ITA Savunma Hedge vs Diğerleri</div>', unsafe_allow_html=True)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="Savunma Hedge Rotasyon", line=dict(color="#0EA5E9", width=2.5)))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="BTC Al-Tut", line=dict(color="#F59E0B", width=1.5, dash="dot")))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Altın Al-Tut", line=dict(color="#D97706", width=1.5, dash="dash")))
    fig2.update_layout(height=350, template="plotly_white", paper_bgcolor="#F8FAFC", plot_bgcolor="#FFFFFF", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)

    # İşlem Günlüğü
    st.markdown('<div class="lk-section">8 Yıllık İşlem Günlüğü</div>', unsafe_allow_html=True)
    st.dataframe(trade_log, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Genel hata: {e}")
