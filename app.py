import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json

st.set_page_config(page_title="Makro Döngü Öncüsü & AI", layout="wide")
st.title("📊 Küresel Risk İştahı ve Bitcoin Döngü Pusulası")

# Secrets üzerinden Telegram verilerini güvenli çekme
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()

def telegram_mesaj_gonder(mesaj):
    if not TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://telegram.org{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

# Canlı Veri Çekme (Hafta sonu korumalı)
@st.cache_data(ttl=3600)
def verileri_getir():
    semboller = {"GC=F": "Altın", "SI=F": "Gümüş", "HG=F": "Bakır", "BTC-USD": "Bitcoin"}
    df = yf.download(list(semboller.keys()), period="2y", interval="1d")
    if 'Close' in df.columns:
        df = df['Close']
    df.rename(columns=semboller, inplace=True)
    df = df.ffill().bfill()
    return df

try:
    data = verileri_getir()
    
    if data.empty or len(data) < 20:
        st.error("Veri havuzu henüz yeterli büyüklükte değil.")
    else:
        # Rasyo ve Hareketli Ortalama Hesaplama
        data['Rasyo'] = data['Altın'] / (data['Gümüş'] + data['Bakır'])
        data['SMA20'] = data['Rasyo'].rolling(window=20).mean()
        data = data.dropna()
        
        son_rasyo = data['Rasyo'].iloc[-1]
        son_sma = data['SMA20'].iloc[-1]
        btc_fiyat = data['Bitcoin'].iloc[-1]
        is_risk_on = son_rasyo < son_sma
        
        # Üst Metrik Kartları
        col1, col2, col3 = st.columns(3)
        col1.metric("Bitcoin Fiyatı", f"${btc_fiyat:,.2f}")
        col2.metric("Metal Rasyosu / SMA20", f"{son_rasyo:.3f} / {son_sma:.3f}")
        
        if is_risk_on:
            status_text = "🟢 REJİM: RISK-ON (Kripto Baharı)"
            col3.success(status_text)
        else:
            status_text = "🔴 REJİM: RISK-OFF (Koruma Dönemi)"
            col3.error(status_text)
            
        # Telegram Butonu
        if st.button("📢 Güncel Durumu Telegram'a Raporla"):
            rapor_mesaji = (
                f"📊 *Günlük Makro Döngü Raporu*\n\n"
                f"🪙 *BTC Fiyatı:* ${btc_fiyat:,.2f}\n"
                f"📈 *Metal Rasyosu:* {son_rasyo:.3f}\n"
                f"📉 *Sinyal Hattı (SMA20):* {son_sma:.3f}\n\n"
                f"🚨 *Piyasa Durumu:* {status_text}"
            )
            telegram_mesaj_gonder(rapor_mesaji)

        # 🚀 TEK GRAFİKTE ÇİFT EKSENLİ BİRLEŞTİRME (Hatasız Güncel Sürüm)
        st.subheader("🔄 Tek Grafikte Zıt Korelasyon (Sol Eksen: BTC / Sağ Eksen: Metal Rasyosu)")
        
        fig = go.Figure()

        # 1. Çizgi: Bitcoin (Sol Y Ekseni)
        fig.add_trace(go.Scatter(
            x=data.index, 
            y=data['Bitcoin'], 
            name="Bitcoin (Sol Eksen)", 
            line=dict(color='orange', width=3)
        ))

        # 2. Çizgi: Metal Rasyosu (Sağ Y Ekseni)
        fig.add_trace(go.Scatter(
            x=data.index, 
            y=data['Rasyo'], 
            name="3'lü Metal Rasyosu (Sağ Eksen)", 
            line=dict(color='black', width=1.5),
            yaxis="y2"
        ))

        # 3. Çizgi: SMA20 (Sağ Y Ekseni)
        fig.add_trace(go.Scatter(
            x=data.index, 
            y=data['SMA20'], 
            name="SMA 20 Sinyal (Sağ Eksen)", 
            line=dict(color='red', width=1, dash='dash'),
            yaxis="y2"
        ))

        # Hataya neden olan 'titlefont' parametreleri güncel 'title_font' ile değiştirildi
        fig.update_layout(
            height=600,
            template="plotly_white",
            xaxis=dict(title="Tarih", linewidth=1, linecolor="gray"),
            yaxis=dict(
                title=dict(text="Bitcoin Fiyatı ($)", font=dict(color="orange")), 
                tickfont=dict(color="orange"),
                side="left"
            ),
            yaxis2=dict(
                title=dict(text="Metal Rasyosu Değeri", font=dict(color="black")), 
                tickfont=dict(color="black"), 
                overlaying="y", 
                side="right",
                anchor="x"
            ),
            legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.5)")
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # YAPAY ZEKA AJANI BÖLÜMÜ
        st.markdown("---")
        st.subheader("🤖 Makro Pusula Yapay Zeka Danışmanı")
        user_question = st.text_input("Yapay Zeka Ajanına bir soru sorun:")
        if user_question:
            with st.spinner("Analiz ediliyor..."):
                try:
                    system_context = f"Sen makro uzmanısın. Güncel durum: BTC ${btc_fiyat:,.2f}, Rasyo {son_rasyo:.3f}, Rejim {status_text}. Tek grafikteki çift eksenli zıt korelasyonu temel alarak rasyonel ve Türkçe yanıt ver."
                    response = requests.post("https://openrouter.ai", 
                        headers={"Authorization": "Bearer free", "Content-Type": "application/json"},
                        data=json.dumps({
                            "model": "meta-llama/llama-3.2-3b-instruct:free",
                            "messages": [{"role": "user", "content": f"{system_context}\n\nKullanıcı: {user_question}"}]
                        }), timeout=10
                    )
                    if response.status_code == 200:
                        st.markdown(f"**🤖 AI Danışmanının Analizi:**\n\n{response.json()['choices']['message']['content']}")
                except:
                    st.warning("Yapay zeka motoru piyasa verilerini inceliyor.")

except Exception as e:
    st.error(f"Veri hesaplanırken genel hata oluştu: {e}")
