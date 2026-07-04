import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
import google.generativeai as genai

# ==============================================================================
# 1. GLOBAL AYARLAR, GÜVENLİK VE PRODÜKSİYON YAPILANDIRMASI
# ==============================================================================
st.set_page_config(
    page_title="Süper Kompozit LMI Likidite Paneli v2",
    layout="wide",
    page_icon="◆",
    initial_sidebar_state="expanded"
)

# [KRİTİK]: API ve Kimlik Bilgilerini Buraya Giriniz
TELEGRAM_TOKEN   = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
GEMINI_API_KEY   = "YOUR_GEMINI_API_KEY"

KONTROL_ARALIK   = 140  # Dakika bazında arka plan kontrol periyodu
STATE_FILE       = Path("lmi_complete_alert_state.json")
CACHE_FILE       = Path("lmi_financial_cache.json")

# Gemini Yapay Zeka Yapılandırması
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    genai.configure(api_key=GEMINI_API_KEY)

# ==============================================================================
# 2. GELİŞMİŞ CSS VE UI TEMA MİMARİSİ (LIGHT THEME)
# ==============================================================================
BG      = "#F4F6FA"
CARD    = "#FFFFFF"
BORDER  = "#E2E6EF"
BORDER2 = "#CBD2E0"
TEXT    = "#1A1D23"
TEXT2   = "#111318"
SUB     = "#6B7280"
MUTEDTX = "#374151"
PLOTBG  = "#FFFFFF"
PLOTTEM = "plotly_white"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&family=JetBrains+Mono:wght=400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; color: {TEXT}; }}

.lk-header {{ padding: 24px 4px 16px 4px; border-bottom: 1px solid {BORDER}; margin-bottom: 25px; }}
.lk-eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; color: #3B82F6; margin-bottom: 6px; }}
.lk-title {{ font-size: 32px; font-weight: 700; color: {TEXT2}; margin: 0; letter-spacing: -0.02em; }}
.lk-subtitle {{ font-size: 14px; color: {SUB}; margin-top: 6px; }}
div[data-testid="stMetric"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
div[data-testid="stMetric"] label {{ color: {SUB} !important; font-size: 11px !important; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }}
div[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-size: 22px !important; font-weight: 700; color: {TEXT2} !important; }}
.lk-regime {{ border-radius: 14px; padding: 16px 22px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 14px; line-height: 1.6; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 20px; }}
.lk-regime-strong-on  {{ background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.4);  color: #16A34A; }}
.lk-regime-weak-on    {{ background: rgba(59,130,246,0.12);  border-color: rgba(59,130,246,0.4);  color: #2563EB; }}
.lk-regime-weak-off   {{ background: rgba(249,115,22,0.12); border-color: rgba(249,115,22,0.4); color: #EA580C; }}
.lk-regime-strong-off {{ background: rgba(239,68,68,0.12);  border-color: rgba(239,68,68,0.4);  color: #DC2626; }}
.lk-section {{ font-size: 16px; font-weight: 700; color: {TEXT2}; margin: 32px 0 14px 0; padding-left: 12px; border-left: 4px solid #3B82F6; letter-spacing: -0.01em; }}
.ai-box {{ background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 14px; padding: 22px; margin-top: 15px; box-shadow: 0 1px 4px rgba(0,0,0,0.01); line-height: 1.7; font-size: 14.5px; }}
.ai-badge {{ background: #EFF6FF; color: #1E40AF; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; font-family: 'JetBrains Mono', monospace; display: inline-block; margin-bottom: 10px; }}
.status-log {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {SUB}; background: #EFA; padding: 6px 12px; border-radius: 6px; display: inline-block; }}
</style>
""", unsafe_allow_html=True)

# Başlık Arayüzü
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">KANTİTATİF MAKRO ROTASYON MOTORU & ASENKRON BİLDİRİM SİSTEMİ</div>
    <p class="lk-title">Süper Kompozit LMI Likidite Paneli</p>
    <p class="lk-subtitle">Bitcoin, Altın, Bakır, Gümüş ve DXY parametrelerini harmanlayan 5 boyutlu kurumsal risk iştahı algoritması</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. MATEMATİKSEL MODEL VE REJİM DETEKTÖRÜ
# ==============================================================================
def rejim_tespit(lmi, s20, s100):
    """
    Yeni Likidite Momentum Endeksi (LMI) değerine göre piyasa rejimini tayin eder.
    LMI yükseldikçe risk iştahı ve likidite artar, düştükçe kriz derinleşir.
    """
    if lmi > s20 and lmi > s100:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢 GÜÇLÜ BOĞA", "Küresel likidite zirvede · Risk iştahı maksimum seviyede")
    elif lmi > s100 and lmi < s20:
        return ("Defansif Boğa", 50, 50, "weak-on", "🔵 DEFANSİF BOĞA", "Ana makro trend yukarı yönlü · Kısa vadeli düzeltme ve konsolidasyon")
    elif lmi < s100 and lmi > s20:
        return ("Erken Uyarı", 0, 100, "weak-off", "🟠 ERKEN UYARI (AYI BAŞLANGICI)", "Ana trend aşağı döndü · Kısa vadeli geçici tepki ve mal boşaltma safhası")
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴 GÜÇLÜ AYI", "Likidite krizi ve agresif DXY baskısı · Tam güvenli liman koruması")

# ==============================================================================
# 4. GELİŞMİŞ VERİ YÖNETİMİ VE HATA İZOLASYONLU VERİ MOTORU
# ==============================================================================
def yerel_cache_yukle():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                data_dict = json.load(f)
                df = pd.DataFrame.from_dict(data_dict)
                df.index = pd.to_datetime(df.index)
                return df
        except: return None
    return None

def yerel_cache_kaydet(df):
    try:
        df_copy = df.copy()
        df_copy.index = df_copy.index.strftime("%Y-%m-%d")
        with open(CACHE_FILE, "w") as f:
            json.dump(df_copy.to_dict(), f)
    except: pass

@st.cache_data(ttl=3600)
def verileri_getir_ve_dogrula():
    symbols = {
        "GC=F": "Altin", 
        "HG=F": "Bakir", 
        "BTC-USD": "Bitcoin", 
        "SI=F": "Gumus", 
        "DX-Y.NYB": "DXY"
    }
    
    # yfinance üzerinden 8 yıllık canlı verinin çekilmesi
    try:
        df = yf.download(list(symbols.keys()), period="8y", interval="1d",
                         auto_adjust=False, multi_level_index=False, progress=False)
        
        if df.empty or "Close" not in df.columns:
            raise ValueError("Yfinance bos veya hatali veri dondu.")
            
        df = df["Close"]
        df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
        
        # Sütun kontrolü ve eksik verilerin ffill/bfill ile temizlenmesi
        cols = ["Altin", "Bakir", "Bitcoin", "Gumus", "DXY"]
        for c in cols:
            if c not in df.columns:
                raise ValueError(f"Eksik sutun saptandi: {c}")
                
        df = df[cols].ffill().bfill()
        yerel_cache_kaydet(df)
        return df
    except Exception as e:
        cached_df = yerel_cache_yukle()
        if cached_df is not None:
            return cached_df
        else:
            st.error(f"Kritik Veri Hatası ve Yerel Önbellek Boş: {e}")
            st.stop()

# ==============================================================================
# 5. GERÇEKÇİ PORTFÖY ROTASYONU VE Gelişmiş ANALİTİK BACKTEST MOTORU
# ==============================================================================
def backtest_rotasyon_motoru(df):
    d = df.copy()
    
    # Yeni Nesil LMI Formülasyonu
    d["LMI"] = ((d["Bitcoin"] / d["Altin"]) * (d["Bakir"] / d["Gumus"])) / d["DXY"]
    
    # Kararlı Makro Trendler İçin Hareketli Ortalamalar
    d["SMA20"] = d["LMI"].rolling(20).mean()
    d["SMA100"] = d["LMI"].rolling(100).mean()
    d = d.dropna().copy()

    # Backtest Değişkenleri
    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    
    trade_rows = []
    equity_curve = []
    btc_pct_track = []
    alt_pct_track = []
    
    btc_duration = alt_duration = combo_duration = 0
    max_portfolio_value = 10000.0
    max_drawdown = 0.0

    for idx, row in d.iterrows():
        lmi, s20, s100 = row["LMI"], row["SMA20"], row["SMA100"]
        bp, ap = float(row["Bitcoin"]), float(row["Altin"])

        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(lmi, s20, s100)
        current_portfolio_value = cash + (btc_qty * bp) + (alt_qty * ap)
        
        # Rejim Değişikliği ve Re-balance Mekanizması
        is_changed = (prev_regime is None) or (isim != prev_regime)

        if is_changed:
            if isim == "Güçlü Boğa":
                btc_qty = current_portfolio_value / bp
                alt_qty = cash = 0.0
            elif isim == "Defansif Boğa":
                btc_qty = (current_portfolio_value * 0.5) / bp
                alt_qty = (current_portfolio_value * 0.5) / ap
                cash = 0.0
            else: # Erken Uyarı veya Güçlü Ayı durumu (%100 Altın Koruma)
                alt_qty = current_portfolio_value / ap
                btc_qty = cash = 0.0

            post_trade_value = cash + (btc_qty * bp) + (alt_qty * ap)
            
            trade_rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Geçiş Senaryosu": f"{prev_regime or 'BAŞLANGIÇ'} ➔ {isim}",
                "Sinyal Durumu": etiket,
                "Hedef Alokasyon": f"BTC %{t_btc} / XAU %{t_alt}",
                "Portföy Değeri ($)": round(post_trade_value, 2),
                "Kümülatif Kar/Zarar": round((post_trade_value / 10000.0 - 1) * 100, 2)
            })
            prev_regime = isim

        # Günlük İstatistik ve Drawdown Takibi
        updated_portfolio_value = cash + (btc_qty * bp) + (alt_qty * ap)
        max_portfolio_value = max(max_portfolio_value, updated_portfolio_value)
        current_dd = (updated_portfolio_value - max_portfolio_value) / max_portfolio_value * 100
        max_drawdown = min(max_drawdown, current_dd)

        if t_btc == 100: btc_duration += 1
        elif t_alt == 100: alt_duration += 1
        else: combo_duration += 1

        equity_curve.append(updated_portfolio_value)
        btc_pct_track.append(t_btc)
        alt_pct_track.append(t_alt)

    d["Portfoy"] = equity_curve
    d["BtcPct"] = btc_pct_track
    d["AltinPct"] = alt_pct_track

    # Derin Analitik Metriklerin Hesaplanması
    toplam_gun = len(d)
    cagr = ((d["Portfoy"].iloc[-1] / 10000.0) ** (252 / toplam_gun) - 1) * 100 if toplam_gun > 0 else 0.0
    
    stats = {
        "islem_sayisi": len(trade_rows),
        "btc_gun": btc_duration,
        "alt_gun": alt_duration,
        "combo_gun": combo_duration,
        "max_dd": round(max_drawdown, 2),
        "toplam_gun": toplam_gun,
        "cagr": round(cagr, 2)
    }
    
    return d, pd.DataFrame(trade_rows), stats

# ==============================================================================
# 6. ASENKRON TELEGRAM BİLDİRİM VE RAPORLAMA KATMANI
# ==============================================================================
def telegram_mesaj_gonder_core(metin):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": metin, "parse_mode": "Markdown"}, timeout=10)
        return r.status_code == 200
    except: return False

def anlik_telegram_raporu_gonder(regime_str, btc_p, xau_p, port_v, cagr_v, mdd_v):
    text = (
        f"◆ *LMI MAKRO LİKİDİTE SİSTEM RAPORU*\n"
        f"────────────────────────\n"
        f"● *Mevcut Piyasa Rejimi:* {regime_str}\n"
        f"● *Anlık Bitcoin Fiyatı:* ${btc_p:,.2f}\n"
        f"● *Anlık Altın Ons Fiyatı:* ${xau_p:,.2f}\n"
        f"● *Strateji Portföy Değeri:* ${port_v:,.2f}\n"
        f"● *Yıllık Bileşik Getiri (CAGR):* %{btc_p:+.2f}\n"
        f"● *Maksimum Tarihsel Erime:* %{mdd_v:.2f}\n"
        f"────────────────────────\n"
        f"⏱ _Raporlama Zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}_"
    )
    return telegram_mesaj_gonder_core(text)

# ==============================================================================
# 7. APSCHEDULER İLE 7/24 ARKA PLAN KONTROL MEKANİZMASI
# ==============================================================================
def arka_plan_sinyal_denetleyici():
    try:
        # Son 150 günün verisini çekerek indikatör tamponunu doldurma
        symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin", "SI=F": "Gumus", "DX-Y.NYB": "DXY"}
        df = yf.download(list(symbols.keys()), period="150d", interval="1d", auto_adjust=False, multi_level_index=False, progress=False)
        if df.empty: return
        
        if "Close" in df.columns: df = df["Close"]
        df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns}).ffill().bfill()
        
        df["LMI"] = ((df["Bitcoin"] / df["Altin"]) * (df["Bakir"] / df["Gumus"])) / df["DXY"]
        df["SMA20"] = df["LMI"].rolling(20).mean()
        df["SMA100"] = df["LMI"].rolling(100).mean()
        
        son_satir = df.dropna().iloc[-1]
        isim, _, _, _, etiket, aciklama = rejim_tespit(son_satir["LMI"], son_satir["SMA20"], son_satir["SMA100"])
        
        eski_rejim = None
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                eski_rejim = json.load(f).get("aktif_rejim")
                
        if eski_rejim != isim:
            with open(STATE_FILE, "w") as f:
                json.dump({"aktif_rejim": isim, "guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f)
                
            alert_msg = (
                f"🚨 *LMI SİNYAL DEĞİŞİKLİĞİ SAKLANDI*\n"
                f"────────────────────────\n"
                f"⚠️ *Yeni Algoritmik Rejim:* {etiket}\n"
                f"ℹ️ *Açıklama:* {aciklama}\n\n"
                f"● *Bitcoin:* ${son_satir['Bitcoin']:,.2f}\n"
                f"● *Altın Ons:* ${son_satir['Altin']:,.2f}\n"
                f"● *DXY Endeksi:* {son_satir['DXY']:.2f}\n"
                f"────────────────────────\n"
                f"🤖 _LMI Asenkron Bekçi Botu Tarafından Gönderildi._"
            )
            telegram_mesaj_gonder_core(alert_msg)
    except: pass

@st.cache_resource
def asenkron_scheduler_baslat():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(arka_plan_sinyal_denetleyici, 'interval', minutes=KONTROL_ARALIK)
    scheduler.start()
    return True

asenkron_scheduler_baslat()

# ==============================================================================
# 8. HATA KORUMALI VE TAMPONLU LLM YAPAY ZEKA MOTORU
# ==============================================================================
if "ai_macro_cache" not in st.session_state:
    st.session_state.ai_macro_cache = None

def gemini_akilli_analiz_tetikle(prompt, is_qa=False):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return "Gemini API Anahtarı eksik veya geçersiz yapılandırılmış."
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        if response and response.text:
            if not is_qa:
                st.session_state.ai_macro_cache = response.text
            return response.text
        return None
    except Exception as e:
        if not is_qa and st.session_state.ai_macro_cache is not None:
            return st.session_state.ai_macro_cache
        return f"Yapay zeka motoru şu an yoğun veya rate-limit sınırında. Hata detayı: {e}"

# ==============================================================================
# 9. INTEGRATED STREAMLIT RUNTIME PIPELINE (ANA PRODÜKSİYON AKIŞI)
# ==============================================================================
try:
    # Veri Çekme ve Model Backtest Çalıştırma
    veri_seti = verileri_getir_ve_dogrula()
    data, trade_log, stats = backtest_rotasyon_motoru(veri_seti)
    
    # Son Durum Verileri
    last_row = data.iloc[-1]
    prev_row = data.iloc[-2]
    
    btc_f = float(last_row["Bitcoin"])
    alt_f = float(last_row["Altin"])
    lmi_f = float(last_row["LMI"])
    s20_f = float(last_row["SMA20"])
    s100_f = float(last_row["SMA100"])
    
    isim_now, btc_p_now, alt_p_now, r_kodu, r_etiket, r_aciklama = rejim_tespit(lmi_f, s20_f, s100_f)
    
    # Karşılaştırma Portföylerinin Oluşturulması (10.000$ Sabit Başlangıç)
    data["BH_BTC"]   = (10000.0 / data["Bitcoin"].iloc[0]) * data["Bitcoin"]
    data["BH_Altin"] = (10000.0 / data["Altin"].iloc[0]) * data["Altin"]
    
    strat_final = float(data["Portfoy"].iloc[-1])
    bh_btc_final = float(data["BH_BTC"].iloc[-1])
    bh_alt_final = float(data["BH_Altin"].iloc[-1])
    
    # Günlük Yüzdesel Değişimler
    btc_chg = ((btc_f / float(prev_row["Bitcoin"])) - 1) * 100
    alt_chg = ((alt_f / float(prev_row["Altin"])) - 1) * 100
    
    # ── METRİK KARTLARI ARAYÜZÜ ───────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Bitcoin (BTCUSD)", f"${btc_f:,.2f}", f"{btc_chg:+.2f}% bugün")
    m2.metric("Altın Ons (XAUUSD)", f"${alt_f:,.2f}", f"{alt_chg:+.2f}% bugün")
    m3.metric("LMI Rotasyon v2 (8Y)", f"${strat_final:,.2f}", f"{((strat_final/10000.0)-1)*100:+.1f}%")
    m4.metric("Sadece BTC Al-Tut", f"${bh_btc_final:,.2f}", f"{((bh_btc_final/10000.0)-1)*100:+.1f}%")
    m5.metric("Sadece Altın Al-Tut", f"${bh_alt_final:,.2f}", f"{((bh_alt_final/10000.0)-1)*100:+.1f}%")
    
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    
    # ── DİNAMİK REJİM BANNERI ─────────────────────────────────────────────────
    st.markdown(f"""
    <div class="lk-regime lk-regime-{r_kodu}">
        <span>{r_etiket} REGREGASYONU</span>
        <span style="font-weight:400; font-size:12.5px; color:#6B7280">{r_aciklama}</span>
        <span style="margin-left:auto; font-size:13.5px;">
            Mevcut Optimal Dağılım: <b style="color:#2563EB">BTC %{btc_p_now}</b> 
            &nbsp;·&nbsp; 
            <b style="color:#EA580C">Altın %{alt_p_now}</b>
        </span>
    </div>""", unsafe_allow_html=True)
    
    # ── YAPAY ZEKA STRATEJİK ANALİZ ALANI ──────────────────────────────────────
    st.markdown('<div class="lk-section">🧠 Gemini AI Profesyonel Makro Analiz İstasyonu</div>', unsafe_allow_html=True)
    
    prompt_taslagi = (
        f"Sen uluslararası saygınlığa sahip bir kantitatif makro hedge fon yöneticisisin. Bitcoin şu an {btc_f} dolar, "
        f"Altın ons fiyatı {alt_f} dolar seviyesinde seyrediyor. Gelişmiş Likidite Momentum Endeksi (LMI) modelimiz şu an '{r_etiket}' modunda "
        f"ve portföy dağılımını dinamik olarak BTC %{btc_p_now} - Altın %{alt_p_now} şeklinde yönetiyor. "
        f"Küresel piyasaların durumunu ve bu iki varlığın 8 yıllık tarihsel döngülerini baz alarak bize 4-6 cümlelik rasyonel ve "
        f"keskin bir makro özet yaz. Metnin en son cümlesi kalıp dışına çıkmadan kelimesi kelimesine tam olarak şu yapıda tek bir cümle "
        f"olmalıdır: 'Şu an ne yapmalı? [Buraya net stratejik tavsiye yazılacak]'."
    )
    
    with st.spinner("Yapay Zeka Makro Analizi Yapılandırılıyor..."):
        ai_response = gemini_akilli_analiz_tetikle(prompt_taslagi, is_qa=False)
        
    if ai_response:
        st.markdown(f"""
        <div class="ai-box">
            <div class="ai-badge">ANALİST RAPORU</div><br>
            {ai_response}
        </div>""", unsafe_allow_html=True)
    else:
        st.warning("Yapay zeka katmanına anlık ulaşılamıyor. Matematiksel model ve alarm bekçileri aktif durumda.")
        
    # ── ETKİLEŞİMLİ SORU CEVAP MODÜLÜ ─────────────────────────────────────────
    st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)
    soru_girdisi = st.text_input("💬 Algoritmaya veya mevcut portföy durumuna dair bir soru sorun (Örn: Değer kayıpları normal mi, sistem nasıl koruyor?):")
    
    if soru_girdisi:
        qa_prompt_taslagi = (
            f"Sen bir kantitatif trade asistanı ve finansal analistsin. Kullanıcının sorusu: '{soru_girdisi}'. "
            f"Mevcut Finansal Matris: Modelimiz '{r_etiket}' rejiminde konumlanmış durumda. Portföy yapısı BTC %{btc_p_now}, Altın %{alt_p_now}. "
            f"Güncel Bitcoin {btc_f}, Altın ons {alt_f}. Bu verilere dayanarak kullanıcının sorusuna finansal rasyonaliteye uygun, "
            f"analitik, dürüst ve güven veren akıcı bir Türkçe ile cevap ver."
        )
        with st.spinner("Analitik yanıt formüle ediliyor..."):
            qa_cevap = gemini_akilli_analiz_tetikle(qa_prompt_taslagi, is_qa=True)
            if qa_cevap:
                st.info(qa_cevap)

    # ── TELEGRAM MANUEL TETİKLEME BUTONU ──────────────────────────────────────
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("📲 Güncel Finansal Durumu Telegram Kanalına Rapor Et"):
        basari = anlik_telegram_raporu_gonder(r_etiket, btc_f, alt_f, strat_final, stats["cagr"], stats["max_dd"])
        if basari:
            st.success("Anlık durum raporu Telegram üzerinden başarıyla iletildi!")
        else:
            st.error("Telegram entegrasyon hatası. API Token veya Chat ID parametrelerini kontrol edin.")

    # ── ALGORİTMİK İSTATİSTİK MATRİSİ ─────────────────────────────────────────
    st.markdown('<div class="lk-section">LMI Model Performans İstatistikleri (Detaylı Matris)</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Toplam Sinyal Değişimi", f"{stats['islem_sayisi']} Sinyal", "Geçiş")
    s2.metric("Bitcoin'de Kalınan Süre", f"{stats['btc_gun']} Gün", f"%{stats['btc_gun']/stats['toplam_gun']*100:.1f}")
    s3.metric("Altın'da Kalınan Süre", f"{stats['alt_gun']} Gün", f"%{stats['alt_gun']/stats['toplam_gun']*100:.1f}")
    s4.metric("Yıllık Bileşik Getiri (CAGR)", f"%{stats['cagr']}", "8 Yıllık Ortalama")
    s5.metric("Maksimum Tarihsel Erime", f"%{stats['max_dd']}", "Drawdown Limiti")

    # ── Gelişmiş RENKLİ BOYAMALI (VSPAN) DETAYLI PLOTLY GRAFİKLERİ ────────────
    st.markdown('<div class="lk-section">Kümülâtif Performans Grafikleri & İndikatör Bölge Analizi</div>', unsafe_allow_html=True)
    
    # 2 Satırlı Subplot Yapısının Kurulması
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.08, subplot_titles=("Portföy Özkaynak Büyüme Eğrileri", "LMI Momentum Endeksi & Sinyal Eşikleri"))
    
    # Üst Grafik: Portföy Karşılaştırmaları
    fig.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="LMI Rotasyon Stratejisi v2", line=dict(color="#22C55E", width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="Sadece BTC Al-Tut", line=dict(color="#F59E0B", width=1.2, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Sadece Altın Al-Tut", line=dict(color="#9CA3AF", width=1.2, dash="dot")), row=1, col=1)
    
    # Alt Grafik: LMI ve Trendleri
    fig.add_trace(go.Scatter(x=data.index, y=data["LMI"], name="LMI Endeks Skoru", line=dict(color="#4B5563", width=1.0)), row=2, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data["SMA20"], name="SMA20 (Kısa Vade Momentum)", line=dict(color="#3B82F6", width=1.3, dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data["SMA100"], name="SMA100 (Makro Trend Filtresi)", line=dict(color="#10B981", width=2.0)), row=2, col=1)

    # Grafik Arka Plan Renklendirme (Rejim Değişimlerinin Grafik Üzerine İşlenmesi)
    # Performans optimizasyonu için rejim geçiş tarihlerini grupluyoruz
    df_reg_changes = data[data["BtcPct"] != data["BtcPct"].shift()]
    change_idx = list(df_reg_changes.index) + [data.index[-1]]
    
    for i in range(len(change_idx) - 1):
        t_start = change_idx[i]
        t_end = change_idx[i+1]
        btc_p_val = data.loc[t_start, "BtcPct"]
        
        # Sinyale göre soft arka plan rengi atama
        if btc_p_val == 100: fill_c = "rgba(34,197,94,0.03)"   # Boğa (Yeşil)
        elif btc_p_val == 50: fill_c = "rgba(59,130,246,0.03)"  # Defansif Boğa (Mavi)
        else: fill_c = "rgba(239,68,68,0.03)"                  # Koruma / Ayı (Kırmızı)
        
        fig.add_vrect(x0=t_start, x1=t_end, fillcolor=fill_c, layer="below", line_width=0, row="all")

    fig.update_layout(
        height=720, template=PLOTTEM, paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT),
        margin=dict(l=15, r=15, t=30, b=15),
        xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
        xaxis2=dict(gridcolor=BORDER), yaxis2=dict(gridcolor=BORDER),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)")
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── TARİHSEL REJİM GEÇİŞ DEFTERİ (LOG TABLE) ──────────────────────────────
    st.markdown('<div class="lk-section">Tarihsel Rejim Geçiş Defteri (Kronolojik Akış)</div>', unsafe_allow_html=True)
    st.dataframe(trade_log.tail(20).iloc[::-1], use_container_width=True, hide_index=True)

except Exception as pipeline_error:
    st.error(f"Sistem Çalışma Zamanı Hatası (Pipeline Error): {pipeline_error}")
