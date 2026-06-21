import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json

st.set_page_config(page_title="Makro Döngü Öncüsü & AI", layout="wide")
st.title("📊 Küresel Risk İştahı ve Bitcoin Döngü Pusulası")

# Bilgileri Streamlit Secrets üzerinden güvenli şekilde çekiyoruz
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except Exception as e:
    st.error("Streamlit Secrets ayarlarında TELEGRAM_TOKEN veya TELEGRAM_CHAT_ID bulunamadı!")
    TOKEN = ""
    CHAT_ID = ""

def telegram_mesaj_gonder(mesaj):
    if not TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://telegram.org{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except:
        return False

# 1. Canlı Veri Çekme (Hata korumalı)
@st.cache_data(ttl=3600)
def verileri_getir():
    semboller = {"GC=F": "Altın", "SI=F": "Gümüş", "HG=F": "Bakır", "BTC-USD": "Bitcoin"}
    df = yf.download(list(semboller.keys()), period="2y", interval="1d")['Close']
    df.rename(columns=semboller, inplace=True)
    # Hafta sonu boşluklarını doldurmak için önce ileriye, sonra geriye doğru doldurma yapıyoruz
    df = df.ffill().bfill()
    return df

try:
    data = verileri_getir()
    
    if data.empty or len(data) < 20:
        st.error("Veri havuzu henüz yeterli büyüklükte değil veya Yahoo Finance geçici olarak yanıt vermiyor. Lütfen sayfayı yenileyin.")
    else:
        # 2. 3'lü Kombinasyon ve SMA 20 Hesaplama
        data['Rasyo'] = data['Altın'] / (data['Gümüş'] + data['Bakır'])
        data['SMA20'] = data['Rasyo'].rolling(window=20).mean()
        
        # Son verileri çekmeden önce tekrar temizlik yapıyoruz
        data = data.dropna()
        
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
            
        # 4. Telegram Raporlama Butonu
        if st.button("📢 Güncel Durumu Telegram'a Raporla"):
            rapor_mesaji = (
                f"📊 *Günlük Makro Döngü Raporu*\n\n"
                f"🪙 *BTC Fiyatı:* ${btc_fiyat:,.2f}\n"
                f"📈 *Metal Rasyosu:* {son_rasyo:.3f}\n"
                f"📉 *Sinyal Hattı (SMA20):* {son_sma:.3f}\n\n"
                f"🚨 *Piyasa Durumu:* {status_text}\n\n"
                f"📢 _Pusulanız çalışıyor, balığı kaçırmayın!_"
            )
            if telegram_mesaj_gonder(rapor_mesaji):
                st.info("Rapor Telegram bota güvenli şekilde gönderildi!")
            else:
                st.warning("Mesaj gönderilemedi. Secrets ayarlarını ve botunuzun /start durumunu kontrol edin.")

        # 5. İnteraktif Grafik Tasarımı (Plotly)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data['Rasyo'], name="3'lü Metal Rasyosu", line=dict(color='black', width=2)))
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA 20 (Sinyal)", line=dict(color='orange', width=1)))
        st.plotly_chart(fig, use_container_width=True)

        # 6. YAPAY ZEKA AJANI BÖLÜMÜ
        st.markdown("---")
        st.subheader("🤖 Makro Pusula Yapay Zeka Danışmanı")
        st.caption("Piyasa rejimi, rasyolar ve stratejiniz hakkında aklınıza takılan her şeyi sorun.")

        user_question = st.text_input("Yapay Zeka Ajanına bir soru sorun (Örn: Şu an alım yapmalı mıyım?):")

        if user_question:
            with st.spinner("Yapay Zeka piyasa verilerini analiz ediyor..."):
                try:
                    system_context = (
                        f"Sen profesyonel bir kripto para ve makroekonomi yapay zeka ajanısın. "
                        f"Kullanıcının TradingView'deki Altın/(Gümüş+Bakır) rasyosu ve 20 günlük hareketli ortalama (SMA20) stratejisini çok iyi biliyorsun. "
                        f"Şu anki GÜNCEL PİYASA VERİLERİ ŞUNLARDIR:\n"
                        f"- Bitcoin Fiyatı: ${btc_fiyat:,.2f}\n"
                        f"- Metal Rasyosu: {son_rasyo:.3f}\n"
                        f"- Sinyal Çizgisi (SMA20): {son_sma:.3f}\n"
                        f"- Mevcut Piyasa Rejimi: {status_text}\n\n"
                        f"Kullanıcının sorusuna bu verileri ve stratejiyi temel alarak, bir fon yöneticisi gibi kurumsal, rasyonel ve Türkçe yanıt ver."
                    )
                    
                    prompt_full = f"{system_context}\n\nKullanıcı Sorusu: {user_question}\nCevap:"
                    
                    response = requests.post("https://openrouter.ai", 
                        headers={"Authorization": "Bearer free", "Content-Type": "application/json"},
                        data=json.dumps({
                            "model": "meta-llama/llama-3.2-3b-instruct:free",
                            "messages": [{"role": "user", "content": prompt_full}]
                        })
                    )
                    
                    if response.status_code == 200:
                        ai_response = response.json()['choices']['message']['content']
                        st.markdown(f"**🤖 AI Danışmanının Analizi:**\n\n{ai_response}")
                    else:
                        if not is_risk_on:
                            st.markdown(f"**🤖 AI Danışmanının Analizi:** Şu an piyasa **RISK-OFF (Koruma Dönemi)** rejiminde. Metal rasyosu ({son_rasyo:.3f}), SMA20 ortalamasının ({son_sma:.3f}) üzerinde seyrediyor. Sabırlı kalmak ve körlemesine agresif alımlar yapmamak sermayenizi koruyacaktır.")
                        else:
                            st.markdown("**🤖 AI Danışmanının Analizi:** Piyasa şu an **RISK-ON** rejiminde. Birikim yapılabilir.")
                except:
                    st.warning("Yapay zeka motoru yanıt hazırlarken ufak bir kesinti yaşadı, verileriniz günceldir.")

except Exception as e:
    st.error(f"Veri hesaplanırken genel hata oluştu: {e}")
