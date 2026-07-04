import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import json
import os
import logging
from datetime import datetime, timedelta
import time

# ==============================================================================
# 1. SİSTEM LOGLAMA VE GLOBAL PRODÜKSİYON YAPILANDIRMASI
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Makro Likidite Kompozit Rotasyon Motoru v1.0",
    layout="wide",
    page_icon="🕋",
    initial_sidebar_state="expanded"
)

# Harici Servis Entegrasyon Noktaları (Environment veya Manuel Değişim)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

# ==============================================================================
# 2. SEÇKİN KURUMSAL LIGHT THEME & ARTIKÜLE ARAYÜZ MİMARİSİ (CSS)
# ==============================================================================
BG_COLOR = "#F1F5F9"
CARD_COLOR = "#FFFFFF"
BORDER_COLOR = "#E2E8F0"
TEXT_COLOR = "#0F172A"
MUTED_TEXT = "#475569"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif;
}}
.stApp {{
    background-color: {BG_COLOR};
    color: {TEXT_COLOR};
}}
.lk-container {{
    background-color: {CARD_COLOR};
    border: 1px solid {BORDER_COLOR};
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}}
.lk-header {{
    padding: 24px 8px;
    border-bottom: 2px solid {BORDER_COLOR};
    margin-bottom: 30px;
}}
.lk-title {{
    font-size: 32px;
    font-weight: 700;
    color: #1E293B;
    letter-spacing: -0.02em;
    margin: 0;
}}
.lk-subtitle {{
    font-size: 14px;
    color: {MUTED_TEXT};
    margin-top: 6px;
}}
.lk-eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #2563EB;
    margin-bottom: 8px;
}}
div[data-testid="stMetric"] {{
    background-color: {CARD_COLOR};
    border: 1px solid {BORDER_COLOR};
    border-radius: 10px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
}}
div[data-testid="stMetricValue"] {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px !important;
    font-weight: 700;
    color: #0F172A !important;
}}
.regime-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    padding: 14px 20px;
    border-radius: 10px;
    font-size: 15px;
    margin-bottom: 25px;
    border: 1px solid;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.rb-bull-heavy    {{ background-color: rgba(34, 197, 94, 0.08); border-color: rgba(34, 197, 94, 0.3); color: #15803D; }}
.rb-bull-light    {{ background-color: rgba(59, 130, 246, 0.08); border-color: rgba(59, 130, 246, 0.3); color: #1D4ED8; }}
.rb-bear-warning {{ background-color: rgba(249, 115, 22, 0.08); border-color: rgba(249, 115, 22, 0.3); color: #C2410C; }}
.rb-bear-panic   {{ background-color: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.3); color: #B91C1C; }}

.section-divider {{
    font-size: 18px;
    font-weight: 700;
    color: #1E293B;
    margin: 35px 0 15px 0;
    padding-left: 10px;
    border-left: 4px solid #2563EB;
}}
</style>
""", unsafe_allow_html=True)

# Main Title Render
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">QUANTITATIVE MACRO LIQUIDITY ENGINE // SYSTEM PROD</div>
    <h1 class="lk-title">Süper Kompozit LMI Likidite Paneli v1.0 Orijinal</h1>
    <p class="lk-subtitle">TradingView Senkronizasyon Altyapılı, Metal Rasyoları, DXY ve M2 Filtreli Kurumsal Portföy Yönetim Simülatörü</p>
</div>
""", unsafe_allow_html=True)

# Session State İlklendirme Blokları (State Güvenliği İçin)
if "session_id" not in st.session_state:
    st.session_state.session_id = str(int(time.time()))
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if "ai_history" not in st.session_state:
    st.session_state.ai_history = []
if "scheduler_active" not in st.session_state:
    st.session_state.scheduler_active = False

# ==============================================================================
# 3. NATIVE HTTP I/O VE İLETİŞİM PROTOKOLLERİ (TELEGRAM & GEMINI CORE)
# ==============================================================================
def execute_telegram_push(payload_text: str) -> bool:
    """Harici bildirim kanalına markdown formatında alarm gönderir."""
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_TOKEN:
        logger.warning("Telegram token tanımsız, push pas geçildi.")
        return False
    
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    headers = {"Content-Type": "application/json"}
    body = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": payload_text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=10)
        return response.status_code == 200
    except Exception as io_err:
        logger.error(f"Telegram push başarısız: {io_err}")
        return False

def query_gemini_brain(prompt_payload: str) -> str:
    """Gelişmiş LLM motoruna kurumsal raporlama çerçevesinde bağlanır."""
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY" or not GEMINI_API_KEY:
        return "Gemini API modülü devre dışı: Geçerli bir anahtar bulunamadı."
    
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    structured_body = {
        "contents": [{
            "parts": [{"text": prompt_payload}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.95,
            "maxOutputTokens": 1024
        }
    }
    try:
        response = requests.post(endpoint, headers=headers, json=structured_body, timeout=20)
        if response.status_code == 200:
            raw_data = response.json()
            return raw_data['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"LLM Ağı Hatası: Durum {response.status_code} - {response.text}"
    except Exception as connection_err:
        return f"LLM Bağlantı Zaman Aşımı: {connection_err}"

# ==============================================================================
# 4. YFINANCE DERİN VERİ HAVUZU VE VERİ DOĞRULAMA (DATA PIPELINE)
# ==============================================================================
@st.cache_data(ttl=1800, show_spinner=False)
def download_macro_universe() -> pd.DataFrame:
    """Tarihsel evreni çeker ve eksik verileri enterpole eder."""
    universe_map = {
        "BTC-USD": "Bitcoin",
        "GC=F": "Altin",
        "HG=F": "Bakir",
        "SI=F": "Gumus",
        "DX-Y.NYB": "DXY"
    }
    tickers = list(universe_map.keys())
    
    try:
        logger.info(f"Yfinance evren indirmesi tetiklendi: {tickers}")
        raw_df = yf.download(
            tickers=tickers,
            period="8y",
            interval="1d",
            auto_adjust=False,
            multi_level_index=False,
            progress=False
        )
        
        if raw_df.empty or "Close" not in raw_df.columns:
            raise ValueError("Kritik veri setleri yfinance üzerinden okunamadı.")
            
        close_matrix = raw_df["Close"].rename(columns=universe_map)
        order_cols = ["Bitcoin", "Altin", "Bakir", "Gumus", "DXY"]
        
        # Sütun varlık kontrolü
        for col in order_cols:
            if col not in close_matrix.columns:
                close_matrix[col] = np.nan
                
        cleaned_df = close_matrix[order_cols].ffill().bfill()
        return cleaned_df
    except Exception as data_err:
        logger.error(f"Veri indirme hattında majör hata: {data_err}")
        return pd.DataFrame()

# ==============================================================================
# 5. ASENKRON PLANLAYICI MİMARİSİ (BACKGROUND JOB SCHEDULER)
# ==============================================================================
def background_sync_task():
    """Arka planda TradingView alarm ve veri sağlığını denetleyen mock iş parçacığı."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[SCHEDULER SYNC] {now_str} - Makro rotasyon motoru sağlığı aktif.")

if not st.session_state.scheduler_active:
    try:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(background_sync_task, 'interval', minutes=15)
        scheduler.start()
        st.session_state.scheduler_active = True
        logger.info("BackgroundScheduler arka plan iş parçacığı başarıyla ayağa kaldırıldı.")
    except Exception as sched_err:
        logger.error(f"Scheduler ilklendirme hatası: {sched_err}")

# ==============================================================================
# 6. GELİŞMİŞ VEKTÖRİZE BACKTEST & HESAPLAMA MOTORU (MATRİS TABANLI)
# ==============================================================================
def process_quantitative_engine(data_frame: pd.DataFrame, initial_equity: float = 10000.0, commission: float = 0.001, slippage: float = 0.0005):
    """
    Tüm indikatörleri, rejim koşullarını, işlem maliyetlerini (komisyon + slippage)
    ve drawdown eğrilerini hesaplayan gelişmiş matematik motoru.
    """
    df_calc = data_frame.copy()
    
    # Kompozit LMI Formülasyonu
    df_calc["LMI"] = ((df_calc["Bitcoin"] / df_calc["Altin"]) * (df_calc["Bakir"] / df_calc["Gumus"])) / df_calc["DXY"]
    df_calc["SMA20"] = df_calc["LMI"].rolling(20).mean()
    df_calc["SMA100"] = df_calc["LMI"].rolling(100).mean()
    
    df_calc = df_calc.dropna().copy()
    
    # Koşul Grupları
    c_strong_bull = (df_calc["LMI"] > df_calc["SMA20"]) & (df_calc["LMI"] > df_calc["SMA100"])
    c_weak_bull   = (df_calc["LMI"] < df_calc["SMA20"]) & (df_calc["LMI"] > df_calc["SMA100"])
    c_warning     = (df_calc["LMI"] > df_calc["SMA20"]) & (df_calc["LMI"] < df_calc["SMA100"])
    
    # Karar Matrislerinin İşlenmesi
    df_calc["Rejim"] = np.select([c_strong_bull, c_weak_bull, c_warning], ["Güçlü Boğa", "Defansif Boğa", "Erken Uyarı"], default="Güçlü Ayı")
    df_calc["BTC_Weight"] = np.select([c_strong_bull, c_weak_bull, c_warning], [1.0, 0.5, 0.0], default=0.0)
    df_calc["XAU_Weight"] = np.select([c_strong_bull, c_weak_bull, c_warning], [0.0, 0.5, 1.0], default=1.0)
    
    # CSS ve Etiket Boyamaları
    df_calc["CssClass"] = np.select([c_strong_bull, c_weak_bull, c_warning], ["bull-heavy", "bull-light", "bear-warning"], default="bear-panic")
    df_calc["Tag"] = np.select([c_strong_bull, c_weak_bull, c_warning], ["🟢 GÜÇLÜ BOĞA", "🔵 DEFANSİF BOĞA", "🟠 ERKEN UYARI"], default="🔴 GÜÇLÜ AYI")
    
    # Günlük Getiri Hesaplamaları
    df_calc["BTC_Return"] = df_calc["Bitcoin"].pct_change().fillna(0)
    df_calc["XAU_Return"] = df_calc["Altin"].pct_change().fillna(0)
    
    # Sinyal Gecikme Filtresi (Shift 1) - Gerçekçi ticaret simülasyonu için
    df_calc["Target_BTC_W"] = df_calc["BTC_Weight"].shift(1).fillna(1.0)
    df_calc["Target_XAU_W"] = df_calc["XAU_Weight"].shift(1).fillna(0.0)
    
    # Günlük Getiri Hesaplamaları
    df_calc["BTC_Return"] = df_calc["Bitcoin"].pct_change().fillna(0)
    df_calc["XAU_Return"] = df_calc["Altin"].pct_change().fillna(0)
    
    # Sinyal Gecikme Filtresi (Shift 1) - Gerçekçi ticaret simülasyonu için
    df_calc["Target_BTC_W"] = df_calc["BTC_Weight"].shift(1).fillna(1.0)
    df_calc["Target_XAU_W"] = df_calc["XAU_Weight"].shift(1).fillna(0.0)
    
    # İşlem Maliyetlerinin Hesaplanması (Sinyal Değişim Noktaları)
    df_calc["Weight_Diff"] = df_calc["Target_BTC_W"].diff().abs().fillna(0)
    df_calc["Trade_Cost"] = df_calc["Weight_Diff"] * (commission + slippage)
    
    # Strateji Net Getirisi
    df_calc["Raw_Strategy_Return"] = (df_calc["Target_BTC_W"] * df_calc["BTC_Return"]) + (df_calc["Target_XAU_W"] * df_calc["XAU_Return"])
    df_calc["Net_Strategy_Return"] = df_calc["Raw_Strategy_Return"] - df_calc["Trade_Cost"]
    
    # Portföy Değeri Kümülatif Çarpım
    df_calc["Portfoy"] = initial_equity * (1.0 + df_calc["Net_Strategy_Return"]).cumprod()
    
    # Benchmark Hesaplamaları
    df_calc["BH_BTC"] = initial_equity * (df_calc["Bitcoin"] / df_calc["Bitcoin"].iloc[0])
    df_calc["BH_XAU"] = initial_equity * (df_calc["Altin"] / df_calc["Altin"].iloc[0])
    
    # Risk Metrikleri (Drawdown)
    df_calc["Peak"] = df_calc["Portfoy"].cummax()
    df_calc["Drawdown"] = (df_calc["Portfoy"] - df_calc["Peak"]) / df_calc["Peak"] * 100
    
    return df_calc

# ==============================================================================
# 7. İSTATİSTİKSEL ANALİZ VE HEDGE FON METRİKLERİ MODÜLÜ
# ==============================================================================
def calculate_advanced_metrics(df_perf: pd.DataFrame):
    """Portföyün Sharpe, MaxDD, CAGR ve volatilite matrislerini üretir."""
    total_days = len(df_perf)
    years = total_days / 252.0
    
    final_value = df_perf["Portfoy"].iloc[-1]
    initial_value = 10000.0
    
    cagr = ((final_value / initial_value) ** (1.0 / years) - 1.0) * 100 if years > 0 else 0.0
    max_dd = df_perf["Drawdown"].min()
    
    daily_returns = df_perf["Net_Strategy_Return"]
    volatility = daily_returns.std() * np.sqrt(252) * 100
    
    # Risksiz faiz oranı %4.0 kabul edilmiştir
    risk_free_daily = 0.04 / 252
    excess_returns = daily_returns - risk_free_daily
    sharpe = (excess_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() != 0 else 0.0
    
    # Sinyal Sayısı
    signals = (df_perf["BTC_Weight"] != df_perf["BTC_Weight"].shift()).sum()
    
    return {
        "CAGR": cagr,
        "MaxDD": max_dd,
        "Volatility": volatility,
        "Sharpe": sharpe,
        "Signals": signals
    }

# ==============================================================================
# 8. ÇALIŞMA ZAMANI İCRA VE VERİ YÜKLEME KONTROLÜ
# ==============================================================================
with st.spinner("Makro Veri Evreni yfinance üzerinden normalize ediliyor..."):
    raw_universe = download_macro_universe()

if raw_universe.empty:
    st.error("Kritik Hata: Finansal veri havuzu doldurulamadı. Lütfen internet bağlantınızı veya yfinance API durumunu kontrol edin.")
    st.stop()

# Kantitatif Motoru Koştur
df_processed = process_quantitative_engine(raw_universe)
metrics = calculate_advanced_metrics(df_processed)

last_bar = df_processed.iloc[-1]
prev_bar = df_processed.iloc[-2]

# Yüzdesel Değişimler
btc_day_change = ((last_bar["Bitcoin"] / prev_bar["Bitcoin"]) - 1.0) * 100
xau_day_change = ((last_bar["Altin"] / prev_bar["Altin"]) - 1.0) * 100
strat_total_change = ((last_bar["Portfoy"] / 10000.0) - 1.0) * 100

# ==============================================================================
# 9. DİNAMİK METRİK KARTLARI VE SİNYAL BANNERI RENDERI
# ==============================================================================
m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

m_col1.metric(
    label="BITCOIN (SPOT USD)",
    value=f"${last_bar['Bitcoin']:,.2f}",
    delta=f"{btc_day_change:+.2f}%"
)
m_col2.metric(
    label="ALTIN ONS (XAUUSD)",
    value=f"${last_bar['Altin']:,.2f}",
    delta=f"{xau_day_change:+.2f}%"
)
m_col3.metric(
    label="LMI STRATEJİ PORTFÖYÜ",
    value=f"${last_bar['Portfoy']:,.2f}",
    delta=f"{strat_total_change:+.1f}% Küm."
)
m_col4.metric(
    label="BENCHMARK: AL-TUT BTC",
    value=f"${last_bar['BH_BTC']:,.2f}"
)
m_col5.metric(
    label="BENCHMARK: AL-TUT XAU",
    value=f"${last_bar['BH_XAU']:,.2f}"
)

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# Aktif Makro Rejim Bilgilendirme Kuşağı
st.markdown(f"""
<div class="regime-badge rb-{last_bar['CssClass']}">
    <div>
        <span>AKTİF STRATEJİK REJİM: </span><strong>{last_bar['Tag']}</strong>
    </div>
    <div style="font-size: 13.5px;">
        Algoritmik Portföy Hedef Dağılımı: 
        <span style='text-decoration: underline;'>Bitcoin %{int(last_bar['BTC_Weight']*100)}</span> / 
        <span style='text-decoration: underline;'>Ons Altın %{int(last_bar['XAU_Weight']*100)}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 10. YAPAY ZEKA LABS VE HARİCİ KANAL TETİKLEME İSTASYONU
# ==============================================================================
st.markdown('<div class="section-divider">🧠 Kurumsal Yapay Zeka Laboratuvarı & Entegrasyon Yönetimi</div>', unsafe_allow_html=True)

ai_col1, ai_col2 = st.columns([3, 2])

with ai_col1:
    st.write("### Gemini AI Makro Analiz Raporu")
    st.info("Aşağıdaki tetikleyici, mevcut piyasa matrisini doğrudan kurumsal yapay zeka modeline göndererek profesyonel bir fon bülteni talep eder.")
    
    if st.button("LLM Piyasa Yorumu Üret / Yenile", key="trigger_ai"):
        ai_prompt = (
            f"Sen küresel bir makro hedge fonunun baş kantitatif analistisin. "
            f"Güncel piyasa durumu: Bitcoin ${last_bar['Bitcoin']:,.2f}, Altın Ons ${last_bar['Altin']:,.2f}, "
            f"Bakır fiyatı: {last_bar['Bakir']}, Gümüş fiyatı: {last_bar['Gumus']}, DXY Endeksi: {last_bar['DXY']:.2f}. "
            f"Vektörize LMI indikatörümüzün ürettiği son rejim sinyali: '{last_bar['Rejim']}' (BTC Ağırlığı: %{int(last_bar['BTC_Weight']*100)}). "
            f"Bize bu verileri, küresel likidite koşullarını ve risk iştahını sentezleyen, kurumsal kalitede 3-4 cümlelik bir fon stratejisi özeti yaz."
        )
        with st.spinner("Gemini nöral ağı ile asenkron iletişim kuruluyor..."):
            ai_response = query_gemini_brain(ai_prompt)
            st.session_state.ai_history.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "text": ai_response
            })
            
    if st.session_state.ai_history:
        latest_ai = st.session_state.ai_history[-1]
        st.markdown(f"""
        <div class="lk-container" style="margin-top: 15px;">
            <span style="font-family:'JetBrains Mono'; font-size:11px; background-color:#EFF6FF; color:#1E40AF; padding:4px 8px; border-radius:4px; font-weight:700;">
                KAYIT: {latest_ai['timestamp']} - ANALİST ÖZETİ
            </span>
            <p style="margin-top:12px; font-size:14.5px; line-height:1.7; color:#334155;">{latest_ai['text']}</p>
        </div>
        """, unsafe_allow_html=True)

with ai_col2:
    st.write("### Harici Haberleşme & Webhook Kontrolleri")
    st.write("Model kararlarını ve sinyal değişikliklerini bağlı uç noktalara manuel veya otomatik olarak pushlayabilirsiniz.")
    
    if st.button("📲 Aktif Sinyal Matrisini Telegram Kanalına Gönder", key="tg_push"):
        tg_text = (
            f"◆ *MAKRO QUANT LMI ALARM SİSTEMİ*\n"
            f"────────────────────\n"
            f"● *Sinyal Durumu:* {last_bar['Tag']}\n"
            f"● *Portföy Değeri:* ${last_bar['Portfoy']:,.2f}\n"
            f"● *Bitcoin Fiyat:* ${last_bar['Bitcoin']:,.2f}\n"
            f"● *Ons Altın Fiyat:* ${last_bar['Altin']:,.2f}\n"
            f"● *DXY Endeks Değeri:* {last_bar['DXY']:.2f}\n"
            f"────────────────────\n"
            f"● *Önerilen Model:* BTC %{int(last_bar['BTC_Weight']*100)} / XAU %{int(last_bar['XAU_Weight']*100)}\n"
            f"────────────────────\n"
            f"⏱ _Sistem Zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}_"
        )
        with st.spinner("Telegram API geçidi zorlanıyor..."):
            if execute_telegram_push(tg_text):
                st.success("Sinyal durum raporu Telegram kanalına başarıyla iletildi!")
            else:
                st.error("Telegram entegrasyon hatası: Lütfen API Token veya Chat ID alanlarını kontrol edin.")

# ==============================================================================
# 11. HEDGE FON METRİKLERİ VE PERFORMANS TABLOSU RENDERI
# ==============================================================================
st.markdown('<div class="section-divider">📈 Gelişmiş Risk & Performans İstatistikleri (Backtest Matrisi)</div>', unsafe_allow_html=True)

col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
col_stat1.metric("Yıllık Bileşik Getiri (CAGR)", f"%{metrics['CAGR']:.2f}")
col_stat2.metric("Maksimum Tarihsel Zarar (MaxDD)", f"%{metrics['MaxDD']:.2f}")
col_stat3.metric("Sharpe Rasyosu (Risk-Adjusted)", f"{metrics['Sharpe']:.2f}")
col_stat4.metric("Yıllıklandırılmış Volatilite", f"%{metrics['Volatility']:.2f}")
col_stat5.metric("Toplam Model Re-balance Sayısı", f"{metrics['Signals']} Sinyal")

# ==============================================================================
# 12. MULTI-SUBPLOT KÜMÜLATİF PERFORMANS GRAFİKLERİ VE VSPAN ALANLARI
# ==============================================================================
st.markdown('<div class="section-divider">📊 Kümülâtif Performans Grafikleri & İndikatör Bölge Analizi</div>', unsafe_allow_html=True)

# Plotly Subplot Düzeni Tasarımı
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    subplot_titles=("Portföy Özkaynak Büyüme Eğrileri (Doğrusal Ölçek)", "LMI Momentum Skoru & Hareketli Ortalama Kırılımları"),
    row_heights=[0.6, 0.4]
)

# Üst Grafik Bileşenleri
fig.add_trace(go.Scatter(x=df_processed.index, y=df_processed["Portfoy"], name="LMI Rotasyon v1", line=dict(color="#22C55E", width=2.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df_processed.index, y=df_processed["BH_BTC"], name="Benchmark: Sadece BTC", line=dict(color="#F59E0B", width=1.2, dash="dash")), row=1, col=1)
fig.add_trace(go.Scatter(x=df_processed.index, y=df_processed["BH_XAU"], name="Benchmark: Sadece Altın", line=dict(color="#94A3B8", width=1.2, dash="dot")), row=1, col=1)

# Alt Grafik Bileşenleri
fig.add_trace(go.Scatter(x=df_processed.index, y=df_processed["LMI"], name="LMI Endeks Puanı", line=dict(color="#475569", width=1.0)), row=2, col=1)
fig.add_trace(go.Scatter(x=df_processed.index, y=df_processed["SMA20"], name="SMA20 Hızlı İvme", line=dict(color="#3B82F6", width=1.3, dash="dash")), row=2, col=1)
fig.add_trace(go.Scatter(x=df_processed.index, y=df_processed["SMA100"], name="SMA100 Makro Trend", line=dict(color="#10B981", width=2.0)), row=2, col=1)

# Akıllı VSPAN (Dikey Bölge) Renklendirme Döngüsü
# Sinyal değişim tarihlerini yakala
signal_changes = df_processed[df_processed["BTC_Weight"] != df_processed["BTC_Weight"].shift()]
change_timestamps = list(signal_changes.index) + [df_processed.index[-1]]

for idx in range(len(change_timestamps) - 1):
    start_t = change_timestamps[idx]
    end_t = change_timestamps[idx+1]
    active_weight = df_processed.loc[start_t, "BTC_Weight"]
    
    if active_weight == 1.0:
        fill_color_zone = "rgba(34, 197, 94, 0.025)"  # Boğa
    elif active_weight == 0.5:
        fill_color_zone = "rgba(59, 130, 246, 0.025)"  # Kararsız / Defansif
    else:
        fill_color_zone = "rgba(239, 68, 68, 0.025)"  # Ayı / Nakit-Altın
        
    fig.add_vrect(x0=start_t, x1=end_t, fillcolor=fill_color_zone, layer="below", line_width=0, row="all")

fig.update_layout(
    height=750,
    template="plotly_white",
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    margin=dict(l=20, r=20, t=35, b=20),
    legend=dict(orientation="h", y=1.05, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)")
)

fig.update_xaxes(gridcolor="#E2E8F0", showgrid=True)
fig.update_yaxes(gridcolor="#E2E8F0", showgrid=True)

st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# 13. KRONOLOJİK REJİM GEÇİŞ DEFTERİ VE LOG AUDIT
# ==============================================================================
st.markdown('<div class="section-divider">📜 Tarihsel Rejim Değişim Defteri (Son 15 Makro Rotasyon)</div>', unsafe_allow_html=True)

# Sinyal tarihlerini filtrele ve temiz bir çıktı dataframe'i oluştur
audit_df = signal_changes.copy()
audit_df["Sinyal Tarihi"] = audit_df.index.strftime("%Y-%m-%d")
audit_df["Net Strateji Değeri"] = audit_df["Portfoy"].map(lambda x: f"${x:,.2f}")
audit_df["Model Dağılımı (BTC/XAU)"] = audit_df.apply(lambda r: f"%{int(r['BTC_Weight']*100)} / %{int(r['XAU_Weight']*100)}", axis=1)

render_cols = ["Sinyal Tarihi", "Tag", "Model Dağılımı (BTC/XAU)", "Net Strateji Değeri"]
st.dataframe(
    audit_df[render_cols].tail(15).iloc[::-1],
    use_container_width=True,
    hide_index=True
)
