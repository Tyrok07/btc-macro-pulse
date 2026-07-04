import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json

# ==============================================================================
# 1. PANEL VE API AYARLARI
# ==============================================================================
st.set_page_config(
    page_title="Süper Kompozit LMI Likidite Paneli v2",
    layout="wide",
    page_icon="◆"
)

TELEGRAM_TOKEN   = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
GEMINI_API_KEY   = "YOUR_GEMINI_API_KEY"

# ==============================================================================
# 2. PREMIUM LIGHT THEME CSS ARAYÜZÜ
# ==============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&family=JetBrains+Mono:wght=400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #F4F6FA; color: #1A1D23; }
.lk-header { padding: 20px 4px; border-bottom: 1px solid #E2E6EF; margin-bottom: 20px; }
.lk-title { font-size: 30px; font-weight: 700; color: #111318; margin: 0; }
.lk-subtitle { font-size: 14px; color: #6B7280; margin-top: 4px; }
div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E2E6EF; border-radius: 12px; padding: 15px; }
.lk-regime { border-radius: 12px; padding: 15px 20px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 14px; margin-bottom: 20px; }
.lk-regime-strong-on  { background: rgba(34,197,94,0.1);  border-color: rgba(34,197,94,0.3);  color: #16A34A; }
.lk-regime-weak-on    { background: rgba(59,130,246,0.1);  border-color: rgba(59,130,246,0.3);  color: #2563EB; }
.lk-regime-weak-off   { background: rgba(249,115,22,0.1); border-color: rgba(249,115,22,0.3); color: #EA580C; }
.lk-regime-strong-off { background: rgba(239,68,68,0.1);  border-color: rgba(239,68,68,0.3);  color: #DC2626; }
.lk-section { font-size: 16px; font-weight: 700; color: #111318; margin: 25px 0 12px 0; padding-left: 10px; border-left: 4px solid #3B82F6; }
.ai-box { background: #FFFFFF; border: 1px solid #E2E6EF; border-radius: 12px; padding: 20px; margin-top: 10px; line-height: 1.6; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="lk-header">
    <p class="lk-title">Süper Kompozit LMI Likidite Paneli v2</p>
    <p class="lk-subtitle">Bitcoin, Altın, Bakır, Gümüş ve DXY tabanlı kurumsal risk iştahı motoru</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. NATIVE API FONKSİYONLARI (KÜTÜPHANESİZ)
# ==============================================================================
def telegram_mesaj_gonder(metin):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN": return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: return requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": metin, "parse_mode": "Markdown"}, timeout=10).status_code == 200
    except: return False

def gemini_api_ile_analiz(prompt):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY": return "API Anahtarı eksik."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        r = requests.post(url, headers={'Content-Type': 'application/json'}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()['candidates'][0]['content']['parts'][0]['text'] if r.status_code == 200 else f"Hata: {r.status_code}"
    except Exception as e: return f"Bağlantı Hatası: {e}"

# ==============================================================================
# 4. GÜVENLİ VERİ VE VEKTÖRİZASYON MOTORU (ASLA ENDEKS HATASI VERMEZ)
# ==============================================================================
@st.cache_data(ttl=3600)
def verileri_yukle():
    symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin", "SI=F": "Gumus", "DX-Y.NYB": "DXY"}
    df = yf.download(list(symbols.keys()), period="8y", interval="1d", auto_adjust=False, multi_level_index=False, progress=False)
    df = df["Close"].rename(columns=symbols).ffill().bfill()
    return df

try:
    df = verileri_yukle()
    
    # 5'li Yeni Nesil LMI Formülü
    df["LMI"] = ((df["Bitcoin"] / df["Altin"]) * (df["Bakir"] / df["Gumus"])) / df["DXY"]
    df["SMA20"] = df["LMI"].rolling(20).mean()
    df["SMA100"] = df["LMI"].rolling(100).mean()
    df = df.dropna().copy()

    # Vektörize Rejim Atama Koşulları (Döngüsüz, Hatasız Hızlı Hesaplama)
    conditions = [
        (df["LMI"] > df["SMA20"]) & (df["LMI"] > df["SMA100"]),
        (df["LMI"] < df["SMA20"]) & (df["LMI"] > df["SMA100"]),
        (df["LMI"] > df["SMA20"]) & (df["LMI"] < df["SMA100"])
    ]
    # Rejim isimleri, BTC oranları ve CSS sınıfları
    df["Rejim"] = np.select(conditions, ["Güçlü Boğa", "Defansif Boğa", "Erken Uyarı"], default="Güçlü Ayı")
    df["BtcPct"] = np.select(conditions, [100, 50, 0], default=0)
    df["AltinPct"] = np.select(conditions, [0, 50, 100], default=100)
    df["CssClass"] = np.select(conditions, ["strong-on", "weak-on", "weak-off"], default="strong-off")
    df["Etiket"] = np.select(conditions, ["🟢 GÜÇLÜ BOĞA", "🔵 DEFANSİF BOĞA", "🟠 ERKEN UYARI", "🔴 GÜÇLÜ AYI"], default="🔴 GÜÇLÜ AYI")

    # Basit ve Hatalardan İzole Edilmiş Portföy Getiri Hesabı
    df["BTC_Ret"] = df["Bitcoin"].pct_change().fillna(0)
    df["XAU_Ret"] = df["Altin"].pct_change().fillna(0)
    
    # Bir önceki günün alokasyonuna göre bugünkü getiriyi hesapla (Sinyal gecikmesini önlemek için shift)
    df["Strat_Ret"] = (df["BtcPct"].shift(1).fillna(100) / 100.0) * df["BTC_Ret"] + (df["AltinPct"].shift(1).fillna(0) / 100.0) * df["XAU_Ret"]
    df["Portfoy"] = 10000.0 * (1.0 + df["Strat_Ret"]).cumprod()
    
    # Karşılaştırma Endeksleri
    df["BH_BTC"] = 10000.0 * (df["Bitcoin"] / df["Bitcoin"].iloc[0])
    df["BH_Altin"] = 10000.0 * (df["Altin"] / df["Altin"].iloc[0])

    # ==============================================================================
    # 5. CANLI VERİ VE METRİKLER
    # ==============================================================================
    last = df.iloc[-1]
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Bitcoin (BTCUSD)", f"${last['Bitcoin']:,.2f}")
    m2.metric("Altın Ons (XAUUSD)", f"${last['Altin']:,.2f}")
    m3.metric("LMI Rotasyon Stratejisi", f"${last['Portfoy']:,.2f}")
    m4.metric("Sadece BTC Al-Tut", f"${last['BH_BTC']:,.2f}")
    m5.metric("Sadece Altın Al-Tut", f"${last['BH_Altin']:,.2f}")

    st.markdown(f"""
    <div class="lk-regime lk-regime-{last['CssClass']}">
        <span>{last['Etiket']} REJİMİ AKTİF</span>
        <span style="margin-left:auto; font-size:13px;">Mevcut Optimal Dağılım: <b>BTC %{last['BtcPct']}</b> / <b>Altın %{last['AltinPct']}</b></span>
    </div>""", unsafe_allow_html=True)

    # ==============================================================================
    # 6. ENTEGRE AI VE TELEGRAM PANELİ
    # ==============================================================================
    st.markdown('<div class="lk-section">🧠 Gemini AI & İletişim Entegrasyonları</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    with c1:
        if st.button("Yapay Zeka Makro Analizini Başlat"):
            p_text = f"Bitcoin {last['Bitcoin']} dolar, Altın {last['Altin']} dolar. 5'li LMI modelimizin son durumu: '{last['Rejim']}'. Buna göre piyasa iştahını özetleyen 3 cümlelik bir uzman yorumu yaz."
            with st.spinner("Gemini API yanıtı bekleniyor..."):
                st.markdown(f'<div class="ai-box">{gemini_api_ile_analiz(p_text)}</div>', unsafe_allow_html=True)
                
    with c2:
        if st.button("📲 Güncel Sinyali Telegram'a Gönder"):
            msg = f"◆ LMI AKTİF SİNYAL RAPORU\n───\n● Rejim: {last['Etiket']}\n● Dağılım: BTC %{last['BtcPct']} / Altın %{last['AltinPct']}\n● BTC Fiyat: ${last['Bitcoin']:,.2f}\n● Strateji Portföyü: ${last['Portfoy']:,.2f}"
            if telegram_mesaj_gonder(msg): st.success("Telegram sinyali başarıyla iletildi!")
            else: st.error("Telegram gönderilemedi. Bilgileri kontrol edin.")

    # ==============================================================================
    # 7. RENKLİ BOYAMALI (VSPAN) PLOTLY GRAFİKLERİ
    # ==============================================================================
    st.markdown('<div class="lk-section">Kümülâtif Performans Grafikleri & İndikatör Bölge Analizi</div>', unsafe_allow_html=True)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("Portföy Büyüme Eğrileri", "LMI Momentum Endeksi"))
    
    fig.add_trace(go.Scatter(x=df.index, y=df["Portfoy"], name="LMI Rotasyon v2", line=dict(color="#22C55E", width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BH_BTC"], name="Sadece BTC", line=dict(color="#F59E0B", width=1.2, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BH_Altin"], name="Sadece Altın", line=dict(color="#9CA3AF", width=1.2, dash="dot")), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df["LMI"], name="LMI Skoru", line=dict(color="#4B5563", width=1.0)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], name="SMA20", line=dict(color="#3B82F6", width=1.3, dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA100"], name="SMA100", line=dict(color="#10B981", width=2.0)), row=2, col=1)

    # Grafik Arka Plan Renklendirmesi (VSPAN)
    changes = df[df["BtcPct"] != df["BtcPct"].shift()]
    change_idx = list(changes.index) + [df.index[-1]]
    for i in range(len(change_idx) - 1):
        t_s, t_e = change_idx[i], change_idx[i+1]
        bp_val = df.loc[t_s, "BtcPct"]
        fill_c = "rgba(34,197,94,0.03)" if bp_val == 100 else ("rgba(59,130,246,0.03)" if bp_val == 50 else "rgba(239,68,68,0.03)")
        fig.add_vrect(x0=t_s, x1=t_e, fillcolor=fill_c, layer="below", line_width=0, row="all")

    fig.update_layout(height=600, template="plotly_white", margin=dict(l=10, r=10, t=25, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # ==============================================================================
    # 8. TARİHSEL DEĞİŞİM LOGU
    # ==============================================================================
    st.markdown('<div class="lk-section">Son Rejim Değişiklikleri Kaydı</div>', unsafe_allow_html=True)
    log_df = df[df["Rejim"] != df["Rejim"].shift()].copy()
    log_df["Tarih"] = log_df.index.strftime("%Y-%m-%d")
    st.dataframe(log_df[["Tarih", "Etiket", "BtcPct", "AltinPct"]].tail(10).iloc[::-1], use_container_width=True, hide_index=True)

except Exception as main_error:
    st.error(f"Sistem Çalışma Zamanı Entegrasyon Hatası: {main_error}")
