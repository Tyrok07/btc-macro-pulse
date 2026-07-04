import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime

# ==============================================================================
# 1. GLOBAL AYARLAR VE PRODÜKSİYON YAPILANDIRMASI
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

# ==============================================================================
# 2. LIGHT THEME UI TASARIMI (CSS ARAYÜZÜ)
# ==============================================================================
BG      = "#F4F6FA"
CARD    = "#FFFFFF"
BORDER  = "#E2E6EF"
TEXT    = "#1A1D23"
TEXT2   = "#111318"
SUB     = "#6B7280"
PLOTBG  = "#FFFFFF"

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
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">KANTİTATİF MAKRO ROTASYON MOTORU</div>
    <p class="lk-title">Süper Kompozit LMI Likidite Paneli</p>
    <p class="lk-subtitle">Bitcoin, Altın, Bakır, Gümüş ve DXY parametrelerini harmanlayan 5 boyutlu risk iştahı algoritması</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. KÜTÜPHANESİZ DOĞRUDAN API (REQUESTS) İLE GEMINI VE TELEGRAM BAĞLANTISI
# ==============================================================================
def telegram_mesaj_gonder(metin):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": metin, "parse_mode": "Markdown"}, timeout=10)
        return r.status_code == 200
    except:
        return False

def gemini_api_ile_analiz(prompt):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return "Gemini API Anahtarı eksik veya geçersiz yapılandırılmış."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['candidates'][0]['content']['parts'][0]['text']
        return f"Gemini API Hatası (Kod: {response.status_code}): {response.text}"
    except Exception as e:
        return f"Yapay zeka motoruna bağlanırken hata oluştu: {e}"

# ==============================================================================
# 4. MATEMATİKSEL MODEL VE REJİM DETEKTÖRÜ
# ==============================================================================
def rejim_tespit(lmi, s20, s100):
    if lmi > s20 and lmi > s100:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢 GÜÇLÜ BOĞA", "Küresel likidite zirvede · Risk iştahı maksimum seviyede")
    elif lmi > s100 and lmi < s20:
        return ("Defansif Boğa", 50, 50, "weak-on", "🔵 DEFANSİF BOĞA", "Ana makro trend yukarı yönlü · Kısa vadeli konsolidasyon")
    elif lmi < s100 and lmi > s20:
        return ("Erken Uyarı", 0, 100, "weak-off", "🟠 ERKEN UYARI (AYI BAŞLANGICI)", "Ana trend aşağı döndü · Kısa vadeli geçici tepki")
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴 GÜÇLÜ AYI", "Likidite krizi ve agresif DXY baskısı · Tam koruma")

# ==============================================================================
# 5. VERİ MOTORU VE YEREL BACKTEST HESAPLAMALARI
# ==============================================================================
@st.cache_data(ttl=3600)
def verileri_hazirla():
    symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin", "SI=F": "Gumus", "DX-Y.NYB": "DXY"}
    df = yf.download(list(symbols.keys()), period="8y", interval="1d", auto_adjust=False, multi_level_index=False, progress=False)
    df = df["Close"].rename(columns=symbols).ffill().bfill()
    return df

try:
    df_raw = verileri_hazirla()
    d = df_raw.copy()
    
    # 5'li Makro LMI Formülü
    d["LMI"] = ((d["Bitcoin"] / d["Altin"]) * (d["Bakir"] / d["Gumus"])) / d["DXY"]
    d["SMA20"] = d["LMI"].rolling(20).mean()
    d["SMA100"] = d["LMI"].rolling(100).mean()
    d = d.dropna().copy()

    # Backtest Simülasyonu (10.000$ Başlangıç)
    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows = []
    equity_curve = []
    btc_pct_track = []
    
    max_portfolio_value = 10000.0
    max_drawdown = 0.0
    btc_gun = alt_gun = 0

    for idx, row in d.iterrows():
        lmi, s20, s100 = row["LMI"], row["SMA20"], row["SMA100"]
        bp, ap = float(row["Bitcoin"]), float(row["Altin"])
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(lmi, s20, s100)
        
        current_val = cash + (btc_qty * bp) + (alt_qty * ap)
        
        if prev_regime is None or isim != prev_regime:
            if isim == "Güçlü Boğa":
                btc_qty = current_val / bp
                alt_qty = cash = 0.0
            elif isim == "Defansif Boğa":
                btc_qty = (current_val * 0.5) / bp
                alt_qty = (current_val * 0.5) / ap
                cash = 0.0
            else:
                alt_qty = current_val / ap
                btc_qty = cash = 0.0
                
            trade_rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'BAŞLANGIÇ'} ➔ {isim}",
                "Sinyal": etiket,
                "Alokasyon": f"BTC %{t_btc} / XAU %{t_alt}",
                "Portföy ($)": round(current_val, 2)
            })
            prev_regime = isim

        updated_val = cash + (btc_qty * bp) + (alt_qty * ap)
        max_portfolio_value = max(max_portfolio_value, updated_val)
        current_dd = (updated_val - max_portfolio_value) / max_portfolio_value * 100
        max_drawdown = min(max_drawdown, current_dd)
        
        if t_btc == 100: btc_gun += 1
        elif t_alt == 100: alt_gun += 1
        
        equity_curve.append(updated_val)
        btc_pct_track.append(t_btc)

    d["Portfoy"] = equity_curve
    d["BtcPct"] = btc_pct_track
    d["BH_BTC"]   = (10000.0 / d["Bitcoin"].iloc[0]) * d["Bitcoin"]
    d["BH_Altin"] = (10000.0 / d["Altin"].iloc[0]) * d["Altin"]

    # ==============================================================================
    # 6. KULLANICI ARAYÜZÜ VE METRİKLER
    # ==============================================================================
    last_row = d.iloc[-1]
    btc_f, alt_f, lmi_f, s20_f, s100_f = float(last_row["Bitcoin"]), float(last_row["Altin"]), float(last_row["LMI"]), float(last_row["SMA20"]), float(last_row["SMA100"])
    isim_now, btc_p_now, alt_p_now, r_kodu, r_etiket, r_aciklama = rejim_tespit(lmi_f, s20_f, s100_f)
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Bitcoin (BTCUSD)", f"${btc_f:,.2f}")
    m2.metric("Altın Ons (XAUUSD)", f"${alt_f:,.2f}")
    m3.metric("LMI Rotasyon v2", f"${d['Portfoy'].iloc[-1]:,.2f}")
    m4.metric("Sadece BTC Al-Tut", f"${d['BH_BTC'].iloc[-1]:,.2f}")
    m5.metric("Sadece Altın Al-Tut", f"${d['BH_Altin'].iloc[-1]:,.2f}")

    st.markdown(f"""
    <div class="lk-regime lk-regime-{r_kodu}">
        <span>{r_etiket} REGREGASYONU</span>
        <span style="font-weight:400; font-size:12.5px; color:#6B7280">{r_aciklama}</span>
        <span style="margin-left:auto; font-size:13.5px;">Optimal Dağılım: <b>BTC %{btc_p_now}</b> / <b>Altın %{alt_p_now}</b></span>
    </div>""", unsafe_allow_html=True)

    # ==============================================================================
    # 7. CHATBOT VE YAPAY ZEKA ALANI
    # ==============================================================================
    st.markdown('<div class="lk-section">🧠 Gemini AI Profesyonel Makro Analiz İstasyonu</div>', unsafe_allow_html=True)
    prompt_text = f"Bitcoin {btc_f} dolar, Altın {alt_f} dolar. LMI modelimiz '{r_etiket}' modunda. Dağılım BTC %{btc_p_now} - Altın %{alt_p_now}. Piyasa durumunu özetleyen ve riskleri belirten 3 cümlelik kurumsal bir makro rapor yaz."
    
    if st.button("Yapay Zeka Analizini Yenile/Tetikle"):
        with st.spinner("Gemini API'ye bağlanılıyor..."):
            ai_res = gemini_api_ile_analiz(prompt_text)
            st.markdown(f'<div class="ai-box"><div class="ai-badge">ANALİST RAPORU</div><br>{ai_res}</div>', unsafe_allow_html=True)

    if st.button("📲 Güncel Durumu Telegram'a Gönder"):
        msg = f"◆ LMI MAKRO SİSTEM RAPORU\n───\n● Rejim: {r_etiket}\n● BTC: ${btc_f:,.2f}\n● Altın: ${alt_f:,.2f}\n● Portföy: ${d['Portfoy'].iloc[-1]:,.2f}"
        if telegram_mesaj_gonder(msg): st.success("Telegram sinyali başarıyla iletildi!")
        else: st.error("Telegram gönderilemedi. Token veya Chat ID eksik.")

    # ==============================================================================
    # 8. GRAFİKLER (GERİ GELDİ VE BOYAMALI)
    # ==============================================================================
    st.markdown('<div class="lk-section">Kümülâtif Performans Grafikleri & İndikatör Bölge Analizi</div>', unsafe_allow_html=True)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("Portföy Büyüme Eğrileri", "LMI Momentum Endeksi"))
    fig.add_trace(go.Scatter(x=d.index, y=d["Portfoy"], name="LMI Rotasyon v2", line=dict(color="#22C55E", width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["BH_BTC"], name="Sadece BTC", line=dict(color="#F59E0B", width=1.2, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["BH_Altin"], name="Sadece Altın", line=dict(color="#9CA3AF", width=1.2, dash="dot")), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=d.index, y=d["LMI"], name="LMI Skoru", line=dict(color="#4B5563", width=1.0)), row=2, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["SMA20"], name="SMA20", line=dict(color="#3B82F6", width=1.3, dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["SMA100"], name="SMA100", line=dict(color="#10B981", width=2.0)), row=2, col=1)

    # Rejim Arka Plan Renklendirmesi
    df_changes = d[d["BtcPct"] != d["BtcPct"].shift()]
    change_idx = list(df_changes.index) + [d.index[-1]]
    for i in range(len(change_idx) - 1):
        t_s, t_e = change_idx[i], change_idx[i+1]
        bp_val = d.loc[t_s, "BtcPct"]
        fill_c = "rgba(34,197,94,0.03)" if bp_val == 100 else ("rgba(59,130,246,0.03)" if bp_val == 50 else "rgba(239,68,68,0.03)")
        fig.add_vrect(x0=t_s, x1=t_e, fillcolor=fill_c, layer="below", line_width=0, row="all")

    fig.update_layout(height=650, template="plotly_white", paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG, margin=dict(l=15, r=15, t=30, b=15))
    st.plotly_chart(fig, use_container_width=True)

    # Tarihsel Günlükler
    st.markdown('<div class="lk-section">Son Rejim Geçişleri</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(trade_rows).tail(10), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Sistem Çalışma Zamanı Hatası: {e}")
