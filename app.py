import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json

st.set_page_config(page_title="8 Yıllık Süper Kompozit Döngü Öncüsü", layout="wide")
st.title("📊 8 Yıllık Süper Kompozit Rasyo ve Tarihsel Al-Sat Simülatörü")

TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()

def telegram_mesaj_gonder(mesaj):
    if not TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://telegram.org{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        return True
    except:
        return False

# 1. Veri Çekme Süresi 2 Yıldan 8 Yıla Çıkarıldı (2018-2026 Arası)
@st.cache_data(ttl=3600)
def verileri_getir():
    semboller = {"GC=F": "Altın", "HG=F": "Bakır", "BTC-USD": "Bitcoin"}
    # period="2y" değeri "8y" yapılarak tüm tarihi geçmiş havuzumuza eklendi
    df = yf.download(list(semboller.keys()), period="8y", interval="1d")
    if 'Close' in df.columns:
        df = df['Close']
    df.rename(columns=semboller, inplace=True)
    df = df.ffill().bfill()
    return df

try:
    data = verileri_getir()
    
    if data.empty or len(data) < 50:
        st.error("Veri havuzu henüz yeterli büyüklükte değil.")
    else:
        # Süper Kompozit Hesaplama
        data['Rasyo'] = data['Altın'] / (data['Bakır'] / data['Bitcoin'])
        
        # 8 Yıllık büyük trendleri hatasız yakalamak için SMA 50 korundu
        data['SMA50'] = data['Rasyo'].rolling(window=50).mean()
        data = data.dropna().copy()
        
        # 💰 8 YILLIK TARİHSEL 10.000 DOLAR SİMÜLASYONU
        bakiye_usd = 10000.0
        btc_adet = 0.0
        pozisyonda_mi = False
        
        for i in range(len(data)):
            anlik_rasyo = data['Rasyo'].iloc[i]
            anlik_sma = data['SMA50'].iloc[i]
            anlik_btc_fiyat = data['Bitcoin'].iloc[i]
            
            # SİNYAL: Risk-On -> BTC AL
            if anlik_rasyo < anlik_sma and not pozisyonda_mi:
                btc_adet = bakiye_usd / anlik_btc_fiyat
                bakiye_usd = 0.0
                pozisyonda_mi = True
                
            # SİNYAL: Risk-Off -> BTC SAT, NAKDE GEÇ
            elif anlik_rasyo >= anlik_sma and pozisyonda_mi:
                bakiye_usd = btc_adet * anlik_btc_fiyat
                btc_adet = 0.0
                pozisyonda_mi = False
        
        toplam_portfoy_degeri = bakiye_usd if not pozisyonda_mi else (btc_adet * data['Bitcoin'].iloc[-1])
        kazanc_yuzdesi = ((toplam_portfoy_degeri - 10000.0) / 10000.0) * 100
        
        son_rasyo = data['Rasyo'].iloc[-1]
        son_sma = data['SMA50'].iloc[-1]
        btc_fiyat = data['Bitcoin'].iloc[-1]
        is_risk_on = son_rasyo < son_sma
        
        # Kartlar
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Bitcoin Fiyatı", f"${btc_fiyat:,.2f}")
        col2.metric("Süper Rasyo / SMA50", f"{son_rasyo:,.1f} / {son_sma:,.1f}")
        
        if is_risk_on:
            status_text = "🟢 REJİM: RISK-ON (Kripto Baharı)"
            col3.success(status_text)
        else:
            status_text = "🔴 REJİM: RISK-OFF (Koruma Dönemi)"
            col3.error(status_text)
            
        col4.metric(
            label="8 Yıllık Strateji Bakiyesi (Giriş: $10K)", 
            value=f"${toplam_portfoy_degeri:,.2f}", 
            delta=f"%{kazanc_yuzdesi:+.2f} Tarihsel Kazanç"
        )
            
        if st.button("📢 Güncel Durumu Telegram'a Raporla"):
            rapor_mesaji = (
                f"⚡ *8 YILLIK TARİHSEL RAPOR* ⚡\n\n"
                f"🪙 *BTC Fiyatı:* ${btc_fiyat:,.2f}\n"
                f"📊 *Süper Rasyo:* {son_rasyo:,.1f}\n"
                f"📈 *Sinyal Hattı (SMA50):* {son_sma:,.1f}\n\n"
                f"🚨 *Piyasa Durumu:* {status_text}\n"
                f"💰 *8 Yıllık Portföy Gücü:* ${toplam_portfoy_degeri:,.2f} (%{kazanc_yuzdesi:+.2f})"
            )
            telegram_mesaj_gonder(rapor_mesaji)

        st.subheader("🔄 8 Yıllık Tarihsel Süper Kompozit Grafik (2018 - 2026)")
        
        fig = go.Figure()

        # 1. Çizgi: Süper Rasyo Hattı (Siyah)
        fig.add_trace(go.Scatter(x=data.index, y=data['Rasyo'], name="Süper Rasyo", line=dict(color='black', width=1.5)))

        # 📊 RENK DEĞİŞTİREN SMA50 ÇİZGİSİ
        data['Renk'] = data.apply(lambda row: 'green' if row['Rasyo'] < row['SMA50'] else 'red', axis=1)
        
        for _, grup in data.groupby((data['Renk'] != data['Renk'].shift()).cumsum()):
            fig.add_trace(go.Scatter(
                x=grup.index,
                y=grup['SMA50'],
                mode='lines',
                line=dict(color=grup['Renk'].iloc, width=3),
                showlegend=False
            ))

        fig.update_layout(
            height=600,
            template="plotly_white",
            xaxis=dict(title="Tarih (8 Yıllık Geniş Perspektif)", linewidth=1, linecolor="gray"),
            yaxis=dict(title="Süper Rasyo Değeri", title_font=dict(color="black"), tickfont=dict(color="black"))
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # YAPAY ZEKA AJANI
        st.markdown("---")
        st.subheader("🤖 Tarihsel Döngü Uzmanı Yapay Zeka Danışmanı")
        user_question = st.text_input("Yapay Zeka Ajanına 8 yıllık bu devasa geçmiş ve strateji hakkında bir soru sorun:")
        if user_question:
            with st.spinner("8 yıllık veri analiz ediliyor..."):
                try:
                    system_context = f"Sen makroekonomi profesörüsün. Kullanıcı 2018-2026 arasındaki 8 yıllık büyük döngüyü açtı. 10.000 dolar bu 8 yıllık sürede işletildi ve şu an ${toplam_portfoy_degeri:,.2f} oldu. Mevcut rejim {status_text}. Bu 8 yıllık muazzam performansı, 2020 boğasını ve bugünkü durumu kapsayarak Türkçe yorumla."
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
                    st.warning("Yapay zeka motoru 8 yıllık verileri tarıyor.")

except Exception as e:
    st.error(f"Veri hesaplanırken genel hata oluştu: {e}")
