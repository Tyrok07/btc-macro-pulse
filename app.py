import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Yerel geliştirme ortamındaki .env dosyasını yükle
load_dotenv()

# ── SAYFA AYARI ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

# Streamlit Secrets veya Ortam Değişkenleri senkronizasyonu
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1E293B; }
    .stApp { background-color: #F8FAFC; }
    .lk-title { font-size: 28px; font-weight: 700; color: #0F172A; margin-bottom: 4px; letter-spacing: -0.5px; }
    .lk-subtitle { font-size: 14px; color: #64748B; margin-bottom: 24px; }
    .lk-card { background: #FFFFFF; padding: 20px; border-radius: 12px; border: 1px solid #E2E8F0; box-shadow: 0 1px 3px rgba(0,0,0,0.02); margin-bottom: 16px; }
    .lk-metric-label { font-size: 12px; font-weight: 500; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; }
    .lk-metric-value { font-size: 24px; font-weight: 600; color: #0F172A; margin-top: 4px; }
    .lk-section { font-size: 16px; font-weight: 600; color: #334155; margin-top: 24px; margin-bottom: 12px; border-left: 3px solid #3B82F6; padding-left: 8px; }
    </style>
""", unsafe_allow_html=True)

# ── VERİ ÇEKME FONKSİYONU ─────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def verileri_getir():
    semboller = {"Altin": "GC=F", "Bakir": "HG=F", "BTC": "BTC-USD"}
    df_list = []
    for isim, sembol in semboller.items():
        ticker = yf.Ticker(sembol)
        df = ticker.history(period="max")["Close"].to_frame(name=isim)
        df_list.append(df)
    
    data = df_list[0].join(df_list[1:], how="inner")
    data = data.sort_index()
    
    # Rasyo Hesabı
    data["Rasyo"] = data["Altin"] / (data["Bakir"] * data["BTC"])
    data["SMA10"] = data["Rasyo"].rolling(window=10).mean()
    data["SMA50"] = data["Rasyo"].rolling(window=50).mean()
    return data.dropna()

# ── GÜVENLİ REJİM TESPİT FONKSİYONU (THRESHOLD EKLENDİ) ──────────────────────
def rejim_tespit(rasyo, sma10, sma50):
    # %1'lik bir emniyet marjı (Threshold) ekleyerek sahte kırılımları engellyoruz
    THRESHOLD = 0.01 
    
    # Güçlü Boğa: Rasyo her iki ortalamanın da bariz altında olmalı
    if rasyo < sma10 * (1 - THRESHOLD) and rasyo < sma50 * (1 - THRESHOLD):
        return "GÜÇLÜ BOĞA", "🟢 GÜÇLÜ BOĞA", 100, 0
    
    # Güçlü Ayı: Rasyo her iki ortalamanın da bariz üstünde olmalı
    elif rasyo > sma10 * (1 + THRESHOLD) and rasyo > sma50 * (1 + THRESHOLD):
        return "GÜÇLÜ AYI", "🔴 GÜÇLÜ AYI", 0, 100
    
    # Kararsız / Ara Bölge: Boğa Eğilimli Düzeltme
    elif rasyo < sma50:
        return "BOĞA DÜZELTME", "🟡 BOĞA + Kısa Düzeltme", 50, 50
    
    # Kararsız / Ara Bölge: Ayı Eğilimli Toparlanma
    else:
        return "AYI TOPARLANMA", "🟠 AYI + Kısa Toparlanma", 25, 75

# ── İYİLEŞTİRİLMİŞ BACKTEST FONKSİYONU ────────────────────────────────────────
def backtest_rotasyon(data):
    # Boş veri koruması
    if data.empty:
        return data, pd.DataFrame()

    portfoy = 10000.0
    nakit = portfoy
    t_btc, t_alt = 0, 0
    pos_btc_usd, pos_alt_usd = 0.0, 0.0
    
    portfoy_serisi = []
    trade_rows = []
    prev_regime = None
    
    # İlk satırdaki başlangıç değerleri
    ilk_satir = data.iloc[0]
    _regime, etiket, btc_p, alt_p = rejim_tespit(ilk_satir["Rasyo"], ilk_satir["SMA10"], ilk_satir["SMA50"])
    
    # Başlangıç dağılımı
    pos_btc_usd = nakit * (btc_p / 100.0)
    pos_alt_usd = nakit * (alt_p / 100.0)
    t_btc = pos_btc_usd / ilk_satir["BTC"]
    t_alt = pos_alt_usd / ilk_satir["Altin"]
    prev_regime = _regime
    
    for idx, row in data.iterrows():
        # Güncel varlık değerlerini hesapla
        mevcut_btc_degeri = t_btc * row["BTC"]
        mevcut_alt_degeri = t_alt * row["Altin"]
        toplam_deger = mevcut_btc_degeri + mevcut_alt_degeri
        portfoy_serisi.append(toplam_deger)
        
        # Güncel sinyali kontrol et
        aktif_rejim, etiket, hedef_btc, hedef_alt = rejim_tespit(row["Rasyo"], row["SMA10"], row["SMA50"])
        
        # Sinyal DEĞİŞTİYSE re-balance (yeniden dengeleme) yap
        if aktif_rejim != prev_regime:
            pos_btc_usd = toplam_deger * (hedef_btc / 100.0)
            pos_alt_usd = toplam_deger * (hedef_alt / 100.0)
            
            t_btc = pos_btc_usd / row["BTC"]
            t_alt = pos_alt_usd / row["Altin"]
            
            getiri_yuzde = ((toplam_deger - 10000.0) / 10000.0) * 100
            
            trade_rows.append({
                "Tarih": idx.strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'Başlangıç'} → {aktif_rejim}",
                "Rejim": etiket,
                "Dağılım": f"BTC %{hedef_btc} · Altın %{hedef_alt}",
                "Portföy": int(toplam_deger),
                "Getiri": round(getiri_yuzde, 1)
            })
            prev_regime = aktif_rejim

    data["Portfoy"] = portfoy_serisi
    
    # Buy & Hold (Al-Tut) Karşılaştırmaları
    data["BH_BTC"] = (data["BTC"] / data["BTC"].iloc[0]) * 10000.0
    data["BH_Altin"] = (data["Altin"] / data["Altin"].iloc[0]) * 10000.0
    
    trade_log = pd.DataFrame(trade_rows)
    if not trade_log.empty:
        trade_log = trade_log.iloc[::-1] # Son işlemleri en üste getir
        
    return data, trade_log

# ── TELEGRAM & ALARM SİSTEMİ ──────────────────────────────────────────────────
def load_alert_state():
    if ALERT_STATE_FILE.exists():
        try:
            with open(ALERT_STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_alert_state(state):
    with open(ALERT_STATE_FILE, "w") as f:
        json.dump(state, f)

def send_telegram_alert(message):
    token = st.secrets.get("TELEGRAM_TOKEN", "")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})
        return r.status_code == 200
    except:
        return False

def check_and_trigger_alerts(data):
    if data.empty:
        return
    son_satir = data.iloc[-1]
    son_tarih_str = data.index[-1].strftime("%Y-%m-%d")
    
    _regime, etiket, _, _ = rejim_tespit(son_satir["Rasyo"], son_satir["SMA10"], son_satir["SMA50"])
    
    state = load_alert_state()
    last_sent_regime = state.get("last_regime", None)
    
    if last_sent_regime != _regime:
        msg = (
            f"🚨 *LİKİDİTE REJİM DEĞİŞİKLİĞİ*\n\n"
            f"📅 *Tarih:* {son_tarih_str}\n"
            f"🔄 *Yeni Durum:* {etiket}\n"
            f"📊 *Rasyo:* {son_satir['Rasyo']:.6f}\n"
            f"📈 *SMA10:* {son_satir['SMA10']:.6f}\n"
            f"📉 *SMA50:* {son_satir['SMA50']:.6f}\n\n"
            f"⚠️ _Portföy dağılımınızı stratejiye uygun olarak güncelleyin._"
        )
        success = send_telegram_alert(msg)
        if success:
            state["last_regime"] = _regime
            state["last_alert_date"] = son_tarih_str
            save_alert_state(state)

# ── UYGULAMA AKIŞI (STREAMLIT ARAYÜZÜ) ────────────────────────────────────────
st.markdown('<div class="lk-title">◆ Likidite Kompozit Paneli</div>', unsafe_allow_html=True)
st.markdown('<div class="lk-subtitle">Altın / (Bakır × Bitcoin) Makro Rejim Takip ve Backtest Modeli</div>', unsafe_allow_html=True)

try:
    data = verileri_getir()
except Exception as e:
    st.error(f"Yahoo Finance bağlantı hatası: {e}")
    st.stop()

# Kritik boş veri kontrolü filtresi
if data.empty:
    st.warning("⚠️ Yahoo Finance'ten şu an temiz veri alınamadı veya piyasa saatleri nedeniyle semboller eşleşmedi. Lütfen sayfayı yenilemeyi deneyin.")
    st.stop()

# Veri başarılıysa hesaplamalara geç
data, trade_log = backtest_rotasyon(data)
check_and_trigger_alerts(data)

# Metrikleri Hesapla (Son Günün Verileri)
son_gun = data.iloc[-1]
mevcut_rejim_kod, mevcut_rejim_etiket, t_btc, t_alt = rejim_tespit(son_gun["Rasyo"], son_gun["SMA10"], son_gun["SMA50"])

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="lk-card"><div class="lk-metric-label">Mevcut Makro Rejim</div><div class="lk-metric-value">{mevcut_rejim_etiket}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="lk-card"><div class="lk-metric-label">Önerilen Dağılım</div><div class="lk-metric-value">BTC %{t_btc} / ALTIN %{t_alt}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="lk-card"><div class="lk-metric-label">Kompozit Rasyo</div><div class="lk-metric-value">{son_gun["Rasyo"]:.6f}</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="lk-card"><div class="lk-metric-label">Model Toplam Getiri</div><div class="lk-metric-value">%{((son_gun["Portfoy"]-10000)/10000)*100:.1f}</div></div>', unsafe_allow_html=True)

# Grafik 1: Rasyo ve Hareketli Ortalamalar
st.markdown('<div class="lk-section">Makro Likidite Rasyosu ve Trend Ortalamaları</div>', unsafe_allow_html=True)
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Altın / (Bakır × BTC)", line=dict(color="#2563EB", width=2)))
fig1.add_trace(go.Scatter(x=data.index, y=data["SMA10"], name="SMA 10 (Hızlı)", line=dict(color="#10B981", width=1.5)))
fig1.add_trace(go.Scatter(x=data.index, y=data["SMA50"], name="SMA 50 (Yavaş)", line=dict(color="#EF4444", width=1.5)))
fig1.update_layout(
    height=400, template="plotly_white", paper_bgcolor="#F8FAFC", plot_bgcolor="#FFFFFF",
    font=dict(family="Inter", color="#1E293B"), margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0")
)
st.plotly_chart(fig1, use_container_width=True)

# Grafik 2: Performans Karşılaştırması
st.markdown('<div class="lk-section">Eşit Başlangıçlı Portföy Performans Simülasyonu (10.000 USD Başlangıç)</div>', unsafe_allow_html=True)
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="Güvenli Rotasyon Stratejisi", line=dict(color="#3B82F6", width=2.5)))
fig2.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="BTC Al-Tut", line=dict(color="#F59E0B", width=1.5, dash="dot")))
fig2.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Altın Al-Tut", line=dict(color="#D97706", width=1.5, dash="dash")))
fig2.update_layout(
    height=350, template="plotly_white", paper_bgcolor="#F8FAFC", plot_bgcolor="#FFFFFF",
    font=dict(family="Inter", color="#1E293B"), margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(title="Portföy Değeri (USD)", gridcolor="#E2E8F0"),
    legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)")
)
st.plotly_chart(fig2, use_container_width=True)

# İşlem Günlüğü
st.markdown('<div class="lk-section">İyileştirilmiş İşlem Günlüğü</div>', unsafe_allow_html=True)
st.dataframe(trade_log, use_container_width=True, hide_index=True)

# Alarm Durumu Metrikleri
st.markdown('<div class="lk-section">Otomatik Alarm Sistemi Durumu</div>', unsafe_allow_html=True)
state = load_alert_state()
if state:
    st.info(f"🔔 Son Telegram uyarısı **{state.get('last_alert_date', 'Bilinmiyor')}** tarihinde **{state.get('last_regime', 'Bilinmiyor')}** rejimi için gönderildi.")
else:
    st.warning("⚠️ Henüz bir Telegram alarm kaydı bulunmuyor veya ilk sinyal bekleniyor.")
