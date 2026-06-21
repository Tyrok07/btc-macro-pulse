import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json

st.set_page_config(page_title="Makro Döngü Öncüsü & AI", layout="wide")
st.title("📊 Küresel Risk İştahı ve Bitcoin Döngü Pusulası")

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
        data['Rasyo'] = data['Altın'] / (data['Gümüş'] + data['Bakır'])
        data['SMA20'] = data['Rasyo'].rolling(window=20).mean()
        data = data.dropna().copy()
        
        # 🚀 10.000 DOLARLIK GEÇMİŞE DÖNÜK AL-SAT SİMÜLASYONU (BACKTEST)
        bakiye_usd = 10000.0
        btc_adet = 0.0
        pozisyonda_mi = False  # True = BTC'deyiz, False = Nakit Dolar'dayız
        
        for i in range(len(data)):
            anlik_rasyo = data['Rasyo'].iloc[i]
            anlik_sma = data['SMA20'].iloc[i]
            anlik_btc_fiyat = data['Bitcoin'].iloc[i]
            
            # SİNYAL: Risk-On (Rasyo < SMA) -> BTC AL
            if anlik_rasyo < anlik_sma and not pozisyonda_mi:
                btc_adet = bakiye_usd / anlik_btc_fiyat
                bakiye_usd = 0.0
                pozisyonda_mi = True
                
            # SİNYAL: Risk-Off (Rasyo >= SMA) -> BTC SAT, DOLARA GEÇ
            elif anlik_rasyo >= anlik_sma and pozisyonda_mi:
                bakiye_usd = btc_adet * anlik_btc_fiyat
                btc_adet = 0.0
                pozisyonda_mi = False
        
        # Eğer simülasyonun sonunda hala BTC'deysek güncel toplam varlığı hesapla
        toplam_portfoy_degeri = bakiye_usd if not pozisyonda_mi else (btc_adet * data['Bitcoin'].iloc[-1])
        kazanc_yuzdesi = ((toplam_portfoy_degeri - 10000.0) / 10000.0) * 100
        
        # Son Veriler
        son_rasyo = data['Rasyo'].iloc[-1]
        son_sma = data['SMA20'].iloc[-1]
        btc_fiyat = data['Bitcoin'].iloc[-1]
        is_risk_on = son_rasyo < son_sma
        
        # Üst Metrik Kartları (4 Kolon Yapıldı)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Bitcoin Fiyatı", f"${btc_fiyat:,.2f}")
        col2.metric("Metal Rasyosu / SMA20", f"{son_rasyo:.3f} / {son_sma:.3f}")
        
        if is_risk_on:
            status_text = "🟢 REJİM: RISK-ON (Kripto Baharı)"
            col3.success(status_text)
        else:
            status_text = "🔴 REJİM: RISK-OFF (Koruma Dönemi)"
            col3.error(status_text)
            
        # 10.000 Dolarlık canı simülasyon kartı
        col4.metric(
            label="Strateji Bakiyesi (Başlangıç: $10K)", 
            value=f"${toplam_portfoy_degeri:,.2f}", 
            delta=f"%{kazanc_yuzdesi:+.2f} Kazanç"
        )
            
        if st.button("📢 Güncel Durumu Telegram'a Raporla"):
            rapor_mesaji = (
                f"📊 *Günlük Makro Döngü Raporu*\n\n"
                f"🪙 *BTC Fiyatı:* ${btc_fiyat:,.2f}\n"
                f"📈 *Metal Rasyosu:* {son_rasyo:.3f}\n"
                f"📉 *Sinyal Hattı (SMA20):* {son_sma:.3f}\n\n"
                f"🚨 *Piyasa Durumu:* {status_text}\n"
                f"💰 *Simülasyon Portföyü:* ${toplam_portfoy_degeri:,.2f} (%{kazanc_yuzdesi:+.2f})"
            )
            telegram_mesaj_gonder(rapor_mesaji)

        st.subheader("🔄 Tek Grafikte Zıt Korelasyon ve Renk Değiştiren Sinyal Hattı")
        
        fig = go.Figure()

        # 1. Çizgi: Bitcoin
        fig.add_trace(go.Scatter(x=data.index, y=data['Bitcoin'], name="Bitcoin (Sol Eksen)", line=dict(color='orange', width=3)))

        # 2. Çizgi: Metal Rasyosu
        fig.add_trace(go.Scatter(x=data.index, y=data['Rasyo'], name="3'lü Metal Rasyosu", line=dict(color='black', width=1.5), yaxis="y2"))

        # 📊 RENK DEĞİŞTİREN SMA ÇİZGİSİ (Parça parça boyama mantığı)
        # Risk-on bölgelerini yeşil, risk-off bölgelerini kırmızı çiziyoruz
        data['Renk'] = data.apply(lambda row: 'green' if row['Rasyo'] < row['SMA20'] else 'red', axis=1)
        
        # Plotly'de çizgi rengini anlık değiştirmek için döngüsel renk grupları tanımlıyoruz
        for rejim_renk, grup in data.groupby((data['Renk'] != data['Renk'].shift()).cumsum()):
            fig.add_trace(go.Scatter(
                x=grup.index,
                y=grup['SMA20'],
                mode='lines',
                line=dict(color=grup['Renk'].iloc[0], width=2),
                showlegend=False,
                yaxis="y2"
            ))

        fig.update_layout(
            height=600,
            template="plotly_white",
            xaxis=dict(title="Tarih", linewidth=1, linecolor="gray"),
            yaxis=dict(title="Bitcoin Fiyatı ($)", titlefont=dict(color="orange"), tickfont=dict(color="orange"), side="left"),
            yaxis2=dict(title="Metal Rasyosu (Yeşil: Risk-On / Kırmızı: Risk-Off)", titlefont=dict(color="black"), tickfont=dict(color="black"), overlaying="y", side="right", anchor="x"),
            legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.5)")
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # YAPAY ZEKA AJANI
        st.markdown("---")
        st.subheader("🤖 Makro Pusula Yapay Zeka Danışmanı")
        user_question = st.text_input("Yapay Zeka Ajanına simülasyon karlılığı veya piyasa hakkında bir soru sorun:")
        if user_question:
            with st.spinner("Analiz ediliyor..."):
                try:
                    system_context = f"Sen makro uzmanısın. Başlangıçtaki 10.000 dolar bu indikatöre göre işletildi ve şu an ${toplam_portfoy_degeri:,.2f} oldu. Güncel piyasa {status_text} modunda. Kullanıcıya bu karlılık performansını ve grafikteki renkli SMA çizgilerini yorumlayan Türkçe bir analiz yap."
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
                    st.warning("Yapay zeka motoru simülasyon verilerini inceliyor.")

except Exception as e:
    st.error(f"Veri hesaplanırken genel hata oluştu: {e}")
