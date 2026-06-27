import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Sayfa yapılandırması
st.set_page_config(page_title="Süper Kompozit Likidite Paneli", layout="wide")

st.title("Süper Kompozit Likidite Paneli")
st.subheader("Metal Rasyosu, DXY ve M2 Para Arzı katmanlarıyla küresel likidite akışını ve Bitcoin döngülerini takip et")

# ==========================================
# 1. VERİ GETİRME FONKSİYONU (GÜÇLENDİRİLMİŞ)
# ==========================================
@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {
        "GC=F": "Altin",       
        "SI=F": "Gumus",       
        "HG=F": "Bakir",       
        "DX-Y.NYB": "DXY",     
        "M2SL": "M2",          # FRED M2 Para Arzı
        "BTC-USD": "Bitcoin"   
    }
    
    # Verileri indiriyoruz
    df = yf.download(list(symbols.keys()), period="8y", interval="1d",
                     auto_adjust=False, multi_level_index=False, progress=False)
    
    if df.empty:
        return pd.DataFrame()
        
    # Sütun yapısını kontrol et ve temizle (Close fiyatlarını al)
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            df = df["Close"].copy()
        else:
            df = df.set_axis(df.columns.get_level_values(0), axis=1)
    elif "Close" in df.columns:
        df = df["Close"]
        
    # Sütun isimlerini Türkçeleştir
    df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
    
    # Tüm gerekli sütunların tabloda olduğundan emin ol
    cols = ["Altin", "Gumus", "Bakir", "DXY", "M2", "Bitcoin"]
    for c in cols:
        if c not in df.columns:
            df[c] = float("nan")
            
    # CRITICAL: M2 aylık geldiği için günlük satırlarda NaN oluşur. 
    # Önce ileriye doğru (ffill), sonra geriye doğru (bfill) doldurarak dropna'da yok olmasını engelliyoruz.
    df = df[cols].ffill().bfill()
    return df

# ==========================================
# 2. MODEL VE BACKTEST FONKSİYONU
# ==========================================
def backtest_tam_likidite_modeli(raw_data):
    if raw_data.empty:
        return pd.DataFrame(), [], {}
        
    d = raw_data.copy()
    
    # Katman 1: Endüstriyel / Değerli Metal Rasyosu (Bakır / Altın) -> Ekonomik Canlılık
    d['Metal_Rasyosu'] = d['Bakir'] / d['Altin']
    
    # Katman 2: Kompozit Likidite Endeksi Skorları
    # DXY ters korelasyon, M2 ve Metal Rasyosu doğru korelasyon mantığıyla normalize edilir (Z-Skor veya Basit Oran)
    d['Metal_Z'] = (d['Metal_Rasyosu'] - d['Metal_Rasyosu'].rolling(30).mean()) / d['Metal_Rasyosu'].rolling(30).std()
    d['DXY_Z'] = (d['DXY'] - d['DXY'].rolling(30).mean()) / d['DXY'].rolling(30).std()
    d['M2_Z'] = (d['M2'] - d['M2'].rolling(30).mean()) / d['M2'].rolling(30).std()
    
    # Kompozit Skor (DXY önünde eksi var çünkü likiditeyi daraltır)
    d['Likidite_Skoru'] = d['M2_Z'] + d['Metal_Z'] - d['DXY_Z']
    
    # Sinyal Üretimi (Örnek: Skor hareketli ortalamasının üzerindeyse AL (1), altındaysa NAKİT (0))
    d['Sinyal_MA'] = d['Likidite_Skoru'].rolling(10).mean()
    d['Sinyal'] = np.where(d['Likidite_Skoru'] > d['Sinyal_MA'], 1, 0)
    d['Sinyal'] = d['Sinyal'].shift(1).fillna(0) # Kusursuz backtest için 1 gün kaydırma
    
    # Getiri Hesaplama
    d['Btc_Getiri'] = d['Bitcoin'].pct_change()
    d['Strateji_Getiri'] = d['Btc_Getiri'] * d['Sinyal']
    
    d['Btc_Kumulatif'] = (1 + d['Btc_Getiri'].fillna(0)).cumprod()
    d['Strateji_Kumulatif'] = (1 + d['Strateji_Getiri'].fillna(0)).cumprod()
    
    # dropna'yı hesaplama bitiminde sadece teknik indikatör boşlukları (rolling pencereleri) için yapıyoruz
    d = d.dropna().copy()
    
    # Basit İstatistikler
    stats = {}
    if not d.empty:
        stats['Toplam_Btc_Getiri'] = (d['Btc_Kumulatif'].iloc[-1] - 1) * 100
        stats['Toplam_Strateji_Getiri'] = (d['Strateji_Kumulatif'].iloc[-1] - 1) * 100
    
    return d, [], stats

# ==========================================
# 3. STREAMLIT ANA ÇALIŞMA AKIŞI
# ==========================================
raw = verileri_getir()

if raw.empty:
    st.error("❌ Yahoo Finance üzerinden ham veriler çekilemedi. Lütfen internet bağlantınızı kontrol edin veya daha sonra tekrar deneyin.")
else:
    # Model hesaplamasını başlat
    data, trade_log, stats = backtest_tam_likidite_modeli(raw)
    
    # CRITICAL FIX: Hata veren satırdan önce veri doluluk kontrolü
    if data.empty:
        st.error("⚠️ Model hesaplama hatası: Zaman serileri (M2, DXY veya Metaller) dropna() aşamasında birbiriyle eşleşmediği için işlenecek veri kalmadı.")
        st.info("Bunun nedeni Yahoo Finance'in hafta sonu veri güncellemelerini geciktirmesi veya M2 tablosundaki eksiklikler olabilir.")
        st.stop() # Uygulamanın kalanını çalıştırmayı durdurarak çökmesini engeller.
        
    # 375. Satır: Artık güvenli bölgedeyiz, out-of-bounds hatası vermez
    last = data.iloc[-1]
    
    # Metrikleri Göster
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Son BTC Fiyatı", f"${last['Bitcoin']:,.2f}")
    col2.metric("Likidite Skoru", f"{last['Likidite_Skoru']:.2f}")
    col3.metric("Mevcut Sinyal", "📈 BTC POZİSYON" if last['Sinyal'] == 1 else "💵 NAKİT / FAİZ")
    col4.metric("Strateji Toplam Getiri", f"%{stats.get('Toplam_Strateji_Getiri', 0):.1f}")
    
    # Grafik Alanı
    st.subheader("Performans Karşılaştırması")
    grafik_data = data[['Btc_Kumulatif', 'Strateji_Kumulatif']].rename(
        columns={'Btc_Kumulatif': 'Sadece Bitcoin Tut', 'Strateji_Kumulatif': 'Likidite Stratejisi'}
    )
    st.line_chart(grafik_data)
    
    # Tablo Detayı
    with st.expander("Son Hesaplanan Veri Detayları (Son 5 Gün)"):
        st.dataframe(data.tail(5))
