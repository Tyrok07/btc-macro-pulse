import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

st.set_page_config(page_title="Makro Döngü Öncüsü", layout="wide")
st.title("📊 Küresel Risk İştahı ve Bitcoin Döngü Pusulası")

# Sizin verdiğiniz Telegram bilgileri koda kalıcı olarak eklendi
TOKEN = "8945445385:AAH2rM1UsRT2bntJM8ToeJz6BTD6nJXRvQA"
CHAT_ID = "445160297"

def telegram_mesaj_gonder(mesaj):
    try:
        url = f"https://telegram.org{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram hatası: {e}")

# 1. Canlı Veri Çekme (Yahoo Finance)
@st.cache_data(ttl=3600)  # Veriyi saatte bir günceller
def verileri_getir():
    semboller = {"GC=F": "Altın", "SI=F": "Gümüş", "HG=F": "Bakır", "BTC-USD": "Bitcoin"}
    df = yf.download(list(semboller.keys()), period="2y", interval="1d")['Close']
    df.rename(columns=semboller, inplace=True)
    return df

try:
    data = verileri_getir().dropna()
    
    # 2. 3'lü Kombinasyon ve SMA 20 Hesaplama
    data['Rasyo'] = data['Altın'] / (data['Gümüş'] + data['Bakır'])
    data['SMA20'] = data['Rasyo'].rolling(window=20).mean()
    
    # Son Durum Analizi
    son_rasyo = data['Rasyo'].iloc[-1]
    son_sma = data['SMA20'].iloc[-1]
    btc_fiyat = data['Bitcoin'].iloc[-1]
    
    is_risk_on = son_rasyo < son_sma
    
    # 3. Streamlit Arayüz Kartları
    col1, col2, col3 = st.columns(3)
    col1.metric("Bitcoin Fiyatı", f"${btc_fiyat:,.2f}")
    col2.metric("Metal Rasyosu / SMA20", f"{son_rasyo:.3f} / {son_sma:.3f}")
    
    if is_risk_on:
        status_text = "🟢 REJİM: RISK-ON (Kripto Baharı)"
        col3.success(status_text)
    else:
        status_text = "🔴 REJİM: RISK-OFF (Koruma Dönemi)"
        col3.error(status_text)
        
    # 4. Telegram Raporlama Butonu (Web panel üzerinden tetiklemek için)
    if st.button("📢 Güncel Durumu Telegram'a Raporla"):
        rapor_mesaji = (
            f"📊 *Günlük Makro Döngü Raporu*\n\n"
            f"🪙 *BTC Fiyatı:* ${btc_fiyat:,.2f}\n"
            f"📈 *Metal Rasyosu:* {son_rasyo:.3f}\n"
            f"📉 *Sinyal Hattı (SMA20):* {son_sma:.3f}\n\n"
            f"🚨 *Piyasa Durumu:* {status_text}\n\n"
            f"📢 _Pusulanız çalışıyor, balığı kaçırmayın!_"
        )
        telegram_mesaj_gonder(rapor_mesaji)
        st.info("Rapor Telegram bota gönderildi!")
        
    # 5. İnteraktif Grafik Tasarımı (Plotly)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Rasyo'], name="3'lü Metal Rasyosu", line=dict(color='black', width=2)))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA 20 (Sinyal)", line=dict(color='orange', width=1)))
    
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Veri yüklenirken hata oluştu: {e}")
