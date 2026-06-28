import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json
from pathlib import Path
from datetime import datetime

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    SCHEDULER_OK = True
except ImportError:
    SCHEDULER_OK = False

# ── SAYFA AYARI ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Likidite Kompozit Paneli Pro", layout="wide", page_icon="◆")

BASE_DIR = Path(__file__).resolve().parent if "__file__\" in globals()" else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

# ── TEMA VE STİL AYARLARI ─────────────────────────────────────────────────────
TEMA = "light"  # "dark" veya "light"

if TEMA == "dark":
    BG, CARD, BORDER, TEXT, TEXT2 = "#0B0E14", "#131722", "#1E2430", "#E6E9EF", "#F2F4F8"
    ACCENT_MINT, ACCENT_ROSE, ACCENT_GOLD = "#00F5D4", "#FF477E", "#FFB703"
else:
    BG, CARD, BORDER, TEXT, TEXT2 = "#F8F9FA", "#FFFFFF", "#E9ECEF", "#212529", "#495057"
    ACCENT_MINT, ACCENT_ROSE, ACCENT_GOLD = "#0A9396", "#AE2012", "#EE9B00"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {BG}; color: {TEXT}; }}
    .metric-card {{ background-color: {CARD}; border: 1px solid {BORDER}; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
    </style>
""", unsafe_allow_html=True)

# ── PARAMETRELER (KAYMA VE KOMİSYON DAHİL) ────────────────────────────────────
ISLEM_MALIYETI = 0.0015  # %0.15 Her rejim geçişinde (Alım/Satım + Kayma) uygulanır.

# ── VERİ ÇEKME FONKSİYONU ─────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def veri_yukle():
    # Pine Script katmanlarına sadık kalarak sembolleri çekiyoruz
    semboller = {
        "Altin": "GC=F",
        "Gumus": "SI=F",
        "Bakir": "HG=F",
        "DXY": "DX-Y.NYB",
        "M2_Sim": "WALCL",  # FED Toplam Varlıkları (M2 Genişlemesini simüle eder)
        "BTC": "BTC-USD"
    }
    
    data = {}
    for isim, ticker in semboller.items():
        ticker_data = yf.Ticker(ticker)
        hist = ticker_data.history(period="8y", interval="1d")
        if not hist.empty:
            data[isim] = hist["Close"]
            
    df = pd.DataFrame(data).dropna()
    df.index = df.index.tz_localize(None)
    
    # 1. KATMAN: Metal Rasyosu Eşitlemesi -> Gold / (Silver + Copper)
    df["Metal_Rasyosu"] = df["Altin"] / (df["Gumus"] + df["Bakir"])
    df["MR_MA"] = df["Metal_Rasyosu"].rolling(20).mean()
    df["Risk_On"] = df["Metal_Rasyosu"] < df["MR_MA"]
    
    # 2. KATMAN: DXY Filtresi
    df["DXY_MA"] = df["DXY"].rolling(20).mean()
    df["DXY_Zayif"] = df["DXY"] < df["DXY_MA"]
    
    # 3. KATMAN: Makro Likidite (FED Bilanço) Filtresi
    df["M2_MA"] = df["M2_Sim"].rolling(20).mean()
    df["M2_Genisleme"] = df["M2_Sim"] > df["M2_MA"]
    
    # KOMBİNASYON: Likidite Skorlaması (0 - 3 Puan)
    df["Likidite_Skoru"] = df["Risk_On"].astype(int) + df["DXY_Zayif"].astype(int) + df["M2_Genisleme"].astype(int)
    
    return df

# ── REJİM TESPİT VE STRATEJİ MOTORU ───────────────────────────────────────────
def rejim_ve_backtest_hesapla(df):
    portfoy = 100000.0
    nakit = portfoy
    btc_adet = 0.0
    altin_adet = 0.0
    
    rejimler = []
    dağılımlar = []
    portfoy_degerleri = []
    aktif_dagilim = "Nakit"
    
    for i in range(len(df)):
        skor = df["Likidite_Skoru"].iloc[i]
        tarih = df.index[i]
        
        # Güncel Fiyatlar
        btc_fiyat = df["BTC"].iloc[i]
        altin_fiyat = df["Altin"].iloc[i]
        
        # Rejim ve Hedef Dağılım Belirleme (Pine Script Sk
