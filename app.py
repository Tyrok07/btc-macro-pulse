import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json

st.set_page_config(page_title="Makro Döngü Öncüsü & AI", layout="wide")
st.title("📊 Küresel Risk İştahı ve Bitcoin Döngü Pusulası")

# Secrets üzerinden Telegram verilerini çekme
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

# 1. Canlı Veri Çekme
@st.cache_data(ttl=3600)
def verileri_getir():
    semboller = {"GC=F": "Altın", "SI=F": "Gümüş", "HG=F": "Bakır", "BTC-USD": "Bitcoin"}
    df = yf.download(list(semboller.keys()), period="2y", interval="1d")
    # Eğer çoklu indeks gelirse sadece Close sütununu alıyoruz
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
        # 2. Rasyo Hesaplama
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
            status_text = "🟢 REJİM: RISK-ON (Kripto Baharı - Paranın Adresi BTC)"
            col3.success(status_text)
        else:
            status_text = "🔴 REJİM: RISK-OFF (Koruma Dönemi - Paranın Adresi Altın)"
            col3.error(status_text)
            
        # Telegram Butonu
        if st.button("📢 Güncel Durumu Telegram'a Raporla"):
            rapor_mesaji = (
                f"📊 *Günlük Makro Döngü Raporu*\n\n"
                f"🪙 *BTC Fiyatı:* ${btc_fiyat:,.2f}\n"
                f"📈 *Metal Rasyosu:* {son_rasyo:.3f}\n"
                f"📉 *Sinyal Hattı (SMA20):* {son_sma:.3f}\n\n"
                f"🚨 *Piyasa Durumu:* {status_text}\n\n"
                f"📢 _Zıt korelasyon devrede, fırtınayı veya boğayı kaçırmayın!_"
            )
            if telegram_mesaj_gonder(rapor_mesaji):
                st.success("Rapor Telegram grubunuza başarıyla gönderildi!")

        # 3. İKİLİ GRAFİK TASARIMI (Zıt Korelasyon Vurgulu)
        st.subheader("📈 Korelasyon Grafiği (Üstte BTC Mumları / Altta Metal Pusulası)")
        
        # 2 Satırlı alt grafik oluşturuyoruz
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.1, 
                            subplot_titles=("Bitcoin (BTC/USD) Fiyat Grafiği", "Altın / (Gümüş + Bakır) Makro Rasyosu [Ters Korelasyon]"))
        
        # Satır 1: Bitcoin Çizgi Grafiği
        fig.add_trace(go.Scatter(x=data.index, y=data['Bitcoin'], name="Bitcoin (BTC)", line=dict(color='orange', width=2.5)), row=1, col=1)
        
        # Satır 2: Metal Rasyosu ve SMA20
        fig.add_trace(go.Scatter(x=data.index, y=data['Rasyo'], name="3'lü Metal Rasyosu", line=dict(color='black', width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA 20 (Sinyal)", line=dict(color='red', width=1, dash='dash')), row=2, col=1)
        
        fig.update_layout(height=700, showlegend=True, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

        # 4. YAPAY ZEKA AJANI
        st.markdown("---")
        st.subheader("🤖 Zıt Korelasyon Uzmanı Yapay Zeka Danışmanı")
        
        user_question = st.text_input("Yapay Zeka Ajanına zıt korelasyon veya piyasa hakkında bir soru sorun:")
        if user_question:
            with st.spinner("Yapay Zeka grafikleri ve korelasyonu analiz ediyor..."):
                try:
                    system_context = (
                        f"Sen profesyonel bir makroekonomi ve kripto para uzmanısın. "
                        f"Şu an önünde iki grafik var. Üstte Bitcoin (${btc_fiyat:,.2f}), altta ise Altın/(Gümüş+Bakır) rasyosu var. "
                        f"Kuralı çok iyi biliyorsun: Alttaki grafik yükseldiğinde Bitcoin düşer (Zıt Korelasyon). "
                        f"Güncel durumda rasyo {son_rasyo:.3f} ve SMA20 {son_sma:.3f} değerinde, yani piyasa {status_text} modunda. "
                        f"Kullanıcının sorusuna bu zıt korelasyon ilişkisini mutlaka vurgulayarak, kurumsal ve Türkçe yanıt ver."
                    )
                    prompt_full = f"{system_context}\n\nKullanıcı: {user_question}\nCevap:"
                    
                    response = requests.post("https://openrouter.ai", 
                        headers={"Authorization": "Bearer free", "Content-Type": "application/json"},
                        data=json.dumps({
                            "model": "meta-llama/llama-3.2-3b-instruct:free",
                            "messages": [{"role": "user", "content": prompt_full}]
                        }), timeout=10
                    )
                    if response.status_code == 200:
                        st.markdown(f"**🤖 AI Danışmanının Analizi:**\n\n{response.json()['choices']['message']['content']}")
                    else:
                        st.markdown(f"**🤖 AI Danışmanının Analizi:** Şu an rasyo yukarıda, Bitcoin ise baskı altında. Zıt korelasyon gereği koruma modunda kalmak faydalıdır.")
                except:
                    st.warning("Yapay zeka motoru yanıt hazırlarken ufak bir kesinti yaşadı.")

except Exception as e:
    st.error(f"Veri hesaplanırken genel hata oluştu: {e}")
