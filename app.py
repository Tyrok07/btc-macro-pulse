import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json
import traceback
from pathlib import Path
from datetime import datetime

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    SCHEDULER_OK = True
except ImportError:
    SCHEDULER_OK = False

# ── SAYFA AYARI ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Likidite Kompozit Paneli v2", layout="wide", page_icon="◆")

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

# ── TEMA VE STİL AYARLARI (Python 3.14 Çakışması Engellendi) ─────────────────────
TEMA = "light"  # "dark" veya "light"

if TEMA == "dark":
    BG = "#0B0E14"; CARD = "#131722"; BORDER = "#1E2430"; BORDER2 = "#2A3140"
    TEXT = "#E6E9EF"; TEXT2 = "#F2F4F8"; SUB = "#828FAD"
    C_BG = "rgba(19,23,34,0.95)"; M_BG = "rgba(11,14,20,0.8)"
else:
    BG = "#FFFFFF"; CARD = "#F8F9FA"; BORDER = "#E9ECEF"; BORDER2 = "#DEE2E6"
    TEXT = "#212529"; TEXT2 = "#000000"; SUB = "#6C757D"
    C_BG = "rgba(248,249,250,0.95)"; M_BG = "rgba(255,255,255,0.8)"

# Python 3.14 için CSS parantezleri çiftlenerek f-string koruması sağlandı
st.markdown(f"""
<style>
    .stApp {{ background-color: {BG}; color: {TEXT}; }}
    h1, h2, h3 {{ color: {TEXT2} !important; font-weight: 700 !important; }}
    .stButton>button {{
        background-color: {CARD}; color: {TEXT}; border: 1px solid {BORDER2};
        border-radius: 6px; padding: 0.5rem 1rem; transition: all 0.2s;
    }}
    .stButton>button:hover {{ border-color: #00D2FF; color: #00D2FF; }}
    .metric-card {{
        background-color: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
        padding: 1.2rem; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }}
    .metric-label {{ color: {SUB}; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.2rem; }}
    .metric-value {{ font-size: 1.6rem; font-weight: 700; color: {TEXT2}; }}
</style>
""", unsafe_allowed_with_html=True)

# ── VERI HAZIRLAMA (TRADINGVIEW İLE %100 SENKRON 3 KATMANLI MODEL) ─────────────
@st.cache_data(ttl=3600)
def veri_hazirla():
    # TradingView indikatöründeki tüm enstrümanlar:
    # Altın, Gümüş, Bakır, DXY, Bitcoin ve M2 Para Arzı (yfinance karşılığı: WM2NS)
    semboller = {
        "Altin": "GC=F", "Gumus": "SI=F", "Bakir": "HG=F", 
        "DXY": "DX-Y.NYB", "M2": "WM2NS", "BTC": "BTC-USD"
    }
    
    dfs = {}
    for ad, ticker in semboller.items():
        try:
            obj = yf.Ticker(ticker)
            df_raw = obj.history(period="max")
            if df_raw.empty:
                if ad == "M2":
                    continue
                st.error(f"Kritik Veri Eksik: {ad} ({ticker}) çekilemedi.")
                return pd.DataFrame()
            dfs[ad] = df_raw[["Close"]].rename(columns={"Close": ad})
        except Exception as e:
            st.error(f"{ad} verisi yüklenirken hata: {e}")
            return pd.DataFrame()
            
    # Ana DataFrame birleştirme (Bitcoin merkezli)
    d = dfs["BTC"]
    for ad in ["Altin", "Gumus", "Bakir", "DXY"]:
        d = d.join(dfs[ad], how="inner")
        
    # M2 verisini haftalıktan günlüğe çekip boşlukları doldurma (ffill)
    if "M2" in dfs:
        d = d.join(dfs["M2"], how="left")
        d["M2"] = d["M2"].ffill().bfill()
    else:
        d["M2"] = 21000000000000  # Alternatif sabit değer
        
    d = d.sort_index()
    
    # KATMAN 1 — METAL RASYOSU (Orijinal TradingView Mantığı)
    d["Rasyo"] = d["Altin"] / (d["Gumus"] + d["Bakir"])
    d["Rasyo_MA"] = d["Rasyo"].rolling(window=20).mean()
    d["Risk_On"] = d["Rasyo"] < d["Rasyo_MA"]
    
    # KATMAN 2 — DOLAR ENDEKSİ (DXY)
    d["DXY_MA"] = d["DXY"].rolling(window=20).mean()
    d["DXY_Zayif"] = d["DXY"] < d["DXY_MA"]
    
    # KATMAN 3 — M2 PARA ARZI GENİŞLEMESİ
    d["M2_MA"] = d["M2"].rolling(window=20).mean()
    d["M2_Genisleme"] = d["M2"] > d["M2_MA"]
    
    # KÜMÜLATİF LİKİDİTE SKORU (0 ile 3 Arası Tam Puan)
    d["Skor"] = d["Risk_On"].astype(int) + d["DXY_Zayif"].astype(int) + d["M2_Genisleme"].astype(int)
    
    # DETAYLI REJİM SİNYALLERİ
    def rejim_belirle(row):
        skor = row["Skor"]
        if skor == 3:
            return "🟢🟢 GÜÇLÜ BOĞA", "BTC %100 · Altın %0"
        elif skor == 2:
            return "🟡🟢 BOĞA + Düzeltme", "BTC %50 · Altın %50"
        elif skor == 1:
            return "🟠🔴 AYI + Kısa Toparlanma", "BTC %25 · Altın %75"
        else:
            return "🔴🔴 GÜÇLÜ AYI", "BTC %0 · Altın %100"
            
    rej_list, dag_list = [], []
    for _, row in d.iterrows():
        rej, dag = rejim_belirle(row)
        rej_list.append(rej)
        dag_list.append(dag)
        
    d["Rejim"] = rej_list
    d["Dağılım"] = dag_list
    return d

# ── %0.15 MALİYET VE SLIPPAGE DAHİL ARALIKLI BACKTEST MOTORU ──────────────────
def backtest_calistir(d, baslangic_kasa=10000, komisyon_orani=0.0015):
    kasa = baslangic_kasa
    btc_adet = 0.0
    ons_altin = 0.0
    
    ilk_satir = d.iloc[0]
    btc_fiyat = ilk_satir["BTC"]
    altin_fiyat = ilk_satir["Altin"]
    
    # İlk Gün Dağılım Dağıtımı
    if ilk_satir["Rejim"] == "🟢🟢 GÜÇLÜ BOĞA":
        btc_adet = (kasa * (1 - komisyon_orani)) / btc_fiyat
        kasa = 0
    elif ilk_satir["Rejim"] == "🟡🟢 BOĞA + Düzeltme":
        btc_adet = (kasa * 0.5 * (1 - komisyon_orani)) / btc_fiyat
        ons_altin = (kasa * 0.5 * (1 - komisyon_orani)) / altin_fiyat
        kasa = 0
    elif ilk_satir["Rejim"] == "🟠🔴 AYI + Kısa Toparlanma":
        btc_adet = (kasa * 0.25 * (1 - komisyon_orani)) / btc_fiyat
        ons_altin = (kasa * 0.75 * (1 - komisyon_orani)) / altin_fiyat
        kasa = 0
    else:
        ons_altin = (kasa * (1 - komisyon_orani)) / altin_fiyat
        kasa = 0
        
    kasa_gecmisi = []
    onceki_rejim = ilk_satir["Rejim"]
    
    for idx, row in d.iterrows():
        mevcut_rejim = row["Rejim"]
        c_btc = row["BTC"]
        c_altin = row["Altin"]
        
        # Sinyal değiştiğinde komisyon kes ve portföyü yeniden dağıt
        if mevcut_rejim != onceki_rejim:
            # HATA DÜZELTİLDİ: Türkçe/bozuk karakter temizlendi (toplam_nakit)
            toplam_nakit = (btc_adet * c_btc + ons_altin * c_altin) * (1 - komisyon_orani)
            btc_adet = 0.0
            ons_altin = 0.0
            
            # Yeni rejime geç (Alış Maliyeti)
            if mevcut_rejim == "🟢🟢 GÜÇLÜ BOĞA":
                btc_adet = (toplam_nakit * (1 - komisyon_orani)) / c_btc
            elif mevcut_rejim == "🟡🟢 BOĞA + Düzeltme":
                btc_adet = (toplam_nakit * 0.5 * (1 - komisyon_orani)) / c_btc
                ons_altin = (toplam_nakit * 0.5 * (1 - komisyon_orani)) / altin_fiyat
            elif mevcut_rejim == "🟠🔴 AYI + Kısa Toparlanma":
                btc_adet = (toplam_nakit * 0.25 * (1 - komisyon_orani)) / c_btc
                ons_altin = (toplam_nakit * 0.75 * (1 - komisyon_orani)) / altin_fiyat
            else:
                ons_altin = (toplam_nakit * (1 - komisyon_orani)) / altin_fiyat
                
            onceki_rejim = mevcut_rejim
            
        guncel_servet = (btc_adet * c_btc) + (ons_altin * c_altin) + kasa
        kasa_gecmisi.append(guncel_servet)
        
    d["Portföy"] = kasa_gecmisi
    d["Getiri"] = ((d["Portföy"] - baslangic_kasa) / baslangic_kasa) * 100
    return d

# ── TELEGRAM ALARM MOTORU & MANUEL TEST FONKSİYONLARI ─────────────────────────
def telegram_gonder(mesaj):
    if "TELEGRAM_TOKEN" in st.secrets and "TELEGRAM_CHAT_ID" in st.secrets:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            r = requests.post(url, json={"chat_id": chat_id, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
            return r.ok
        except Exception:
            return False
    return False

def anlik_kontrol_ve_alarm():
    d = veri_hazirla()
    if d.empty: return
    son_satir = d.iloc[-1]
    guncel_rejim = son_satir["Rejim"]
    
    state = {}
    if ALERT_STATE_FILE.exists():
        try:
            with open(ALERT_STATE_FILE, "r") as f: state = json.load(f)
        except: pass
        
    if state.get("son_rejim") != guncel_rejim:
        tarih_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rapor = (
            f"🚨 *LİKİDİTE REJİM DEĞİŞİKLİĞİ (PANEL v2)*\n"
            f"📅 Zaman: {tarih_str}\n"
            f"🔄 Geçiş: {state.get('son_rejim', 'BAŞLANGIÇ')} → {guncel_rejim}\n"
            f"📊 Yeni Dağılım Planı: {son_satir['Dağılım']}\n"
            f"💰 Güncel BTC Fiyatı: ${son_satir['BTC']:.2f}"
        )
        if telegram_gonder(rapor):
            state["son_rejim"] = guncel_rejim
            with open(ALERT_STATE_FILE, "w") as f: json.dump(state, f)

if SCHEDULER_OK and "scheduler_calisiyor" not in st.session_state:
    scheduler = BackgroundScheduler()
    scheduler.add_job(anlik_kontrol_ve_alarm, 'interval', minutes=60)
    scheduler.start()
    st.session_state["scheduler_calisiyor"] = True

# ── PANEL ARAYÜZÜ ─────────────────────────────────────────────────────────────
try:
    st.title("◆ Likidite Kompozit Paneli & Döngü Öncüsü")
    st.caption("TradingView İndikatör Sinyalleri ile Tam Uyumlu Canlı İzleme Modülü")
    
    df = veri_hazirla()
    
    if not df.empty:
        df = backtest_calistir(df)
        son = df.iloc[-1]
        
        # Metrik Kartları Tasarımı
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">GÜNCEL MAKRO REJİM</div><div class="metric-value">{son["Rejim"]}</div></div>', unsafe_allowed_with_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">ÖNERİLEN ROTASYON</div><div class="metric-value" style="font-size:1.15rem;">{son["Dağılım"]}</div></div>', unsafe_allowed_with_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">METAL RASYOSU (GOLD/SI+CU)</div><div class="metric-value">{"✅ RISK-ON" if son["Risk_On"] else "❌ RISK-OFF"}</div></div>', unsafe_allowed_with_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">KÜRESEL LİKİDİTE SKORU</div><div class="metric-value">{int(son["Skor"])} / 3</div></div>', unsafe_allowed_with_html=True)
            
        # Grafik Alanı
        st.subheader("📈 Gerçekçi Kümülatif Getiri Eğrisi")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Portföy"], name="Model Getirisi (%0.15 Komisyonlu)", line=dict(color="#00D2FF", width=2.5)))
        fig.update_layout(
            margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor=BG, plot_bgcolor=BG,
            font=dict(color=TEXT), xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Orijinal Kodundaki Telegram Ayar Bölümü ve Buton Yönetimi
        st.sidebar.subheader("⚙️ Telegram Ayarları ve Test")
        if st.sidebar.button("Telegram Test Mesajı Gönder"):
            basari = telegram_gonder("🔔 Likidite Panel v2 üzerinden test mesajı başarıyla tetiklendi!")
            if basari: st.sidebar.success("Test Mesajı Gönderildi!")
            else: st.sidebar.error("Bağlantı Başarısız! Secrets kontrol edin.")
            
        # ── AI CO-PILOT ───────────────────────────────────────────────────────
        st.subheader("🤖 Makro Likidite Co-Pilot")
        soru = st.text_input("Model rejimlerine veya makro verilere dair bir soru yöneltin:")
        
        if soru and "GEMINI_API_KEY" in st.secrets:
            system_instruction = (
                "Sen 'Likidite Kompozit Modeli' için geliştirilmiş uzman bir finansal yapay zeka asistanısın. "
                "Kullanıcının sorularına sadece Metal Rasyosu, DXY, küresel likidite ve portföy rotasyonu "
                "çerçevesinde yanıt vermelisin. Yatırım tavsiyesi vermeden, eldeki verilere ve kurallara sadık kal."
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={st.secrets['GEMINI_API_KEY']}"
            payload = {"contents": [{"parts": [{"text": f"{system_instruction}\n\nDurum: Rejim={son['Rejim']}, Dağılım={son['Dağılım']}\nSoru: {soru}"}]}]}
            try:
                r = requests.post(url, json=payload, timeout=15)
                if r.ok: st.info(r.json()['candidates'][0]['content']['parts'][0]['text'])
            except Exception as e: st.error(f"AI Hata: {e}")

        # Tarihsel İşlem Geçmişi Çıktısı (Export CSV Formatı İçin)
        st.subheader("📋 Son Rejim Değişim Geçmişi")
        degisimler = df[df["Rejim"] != df["Rejim"].shift(1)].tail(15)
        st.dataframe(degisimler[["Rejim", "Dağılım", "BTC", "Altin", "Portföy", "Getiri"]])
        
        # Manuel CSV İndirme Butonu (Orijinal Özellik)
        csv_data = degisimler.to_csv().encode('utf-8')
        st.download_button("İşlem Geçmişini CSV Olarak İndir", csv_data, "likidite_export.csv", "text/csv")

except Exception as e:
    st.error(f"Sistem Hatası: {e}")
    st.text(traceback.format_exc())
