import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json
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

# ── TEMA VE STİL AYARLARI ─────────────────────────────────────────────────────
TEMA = "light"  # "dark" veya "light" yapabilirsiniz

if TEMA == "dark":
    BG = "#0B0E14"; CARD = "#131722"; BORDER = "#1E2430"; BORDER2 = "#2A3140"
    TEXT = "#E6E9EF"; TEXT2 = "#F2F4F8"; SUB = "#828FAD"
    C_BG = "rgba(19,23,34,0.95)"; M_BG = "rgba(11,14,20,0.8)"
else:
    BG = "#FFFFFF"; CARD = "#F8F9FA"; BORDER = "#E9ECEF"; BORDER2 = "#DEE2E6"
    TEXT = "#212529"; TEXT2 = "#000000"; SUB = "#6C757D"
    C_BG = "rgba(248,249,250,0.95)"; M_BG = "rgba(255,255,255,0.8)"

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

# ── VERİ ÇEKME VE REJİM HESAPLAMA (TRADINGVIEW İLE BİREBİR SENKRON) ────────────
@st.cache_data(ttl=3600)
def veri_hazirla():
    # Semboller: Altın (GC=F), Gümüş (SI=F), Bakır (HG=F), DXY (DX-Y.NYB), Bitcoin (BTC-USD)
    # Not: Gerçek M2 verisi günlük olmadığı veya yfinance'te gecikmeli olduğu için model 
    # TradingView'daki 3 katmanlı yapıyı majör emtia ve DXY likiditesi üzerinden kurar.
    semboller = {
        "Altin": "GC=F", "Gumus": "SI=F", "Bakir": "HG=F", 
        "DXY": "DX-Y.NYB", "BTC": "BTC-USD"
    }
    
    dfs = {}
    for ad, ticker in semboller.items():
        obj = yf.Ticker(ticker)
        df_raw = obj.history(period="max")
        if df_raw.empty:
            st.error(f"{ad} verisi yfinance üzerinden çekilemedi.")
            return pd.DataFrame()
        dfs[ad] = df_raw[["Close"]].rename(columns={"Close": ad})
        
    # Verileri ortak tarihte birleştirme
    d = dfs["BTC"]
    for ad in ["Altin", "Gumus", "Bakir", "DXY"]:
        d = d.join(dfs[ad], how="inner")
        
    d = d.sort_index()
    
    # KATMAN 1: Metal Rasyosu ve SMA (TradingView: ratio = gold / (silver + copper))
    d["Rasyo"] = d["Altin"] / (d["Gumus"] + d["Bakir"])
    d["Rasyo_MA"] = d["Rasyo"].rolling(window=20).mean()
    d["Risk_On"] = d["Rasyo"] < d["Rasyo_MA"]
    
    # KATMAN 2: DXY ve SMA (TradingView: dxy < dxy_ma => dxy_weak)
    d["DXY_MA"] = d["DXY"].rolling(window=20).mean()
    d["DXY_Zayif"] = d["DXY"] < d["DXY_MA"]
    
    # LİKİDİTE SKORU (0 ile 2 arası kümülatif skor)
    # İki katman da olumluysa Skor = 2, biri olumluysa 1, hiçbiri değilse 0
    d["Skor"] = d["Risk_On"].astype(int) + d["DXY_Zayif"].astype(int)
    
    # REJİM TANIMLAMA
    def rejim_belirle(row):
        skor = row["Skor"]
        if skor == 2:
            return "🟢🟢 GÜÇLÜ BOĞA", "BTC %100 · Altın %0"
        elif skor == 1:
            return "🟡🟢 BOĞA + Kısa Düzeltme", "BTC %50 · Altın %50"
        else:
            return "🔴🔴 GÜÇLÜ AYI", "BTC %0 · Altın %100"
            
    rej_list = []
    dag_list = []
    for _, row in d.iterrows():
        rej, dag = rejim_belirle(row)
        rej_list.append(rej)
        dag_list.append(dag)
        
    d["Rejim"] = rej_list
    d["Dagilim"] = dag_list
    return d

# ── MALIYET / KAYMA DAHİL BACKTEST MOTORU ────────────────────────────────────
def backtest_calistir(d, baslangic_kasa=10000, komisyon_orani=0.0015):
    """
    komisyon_orani = 0.0015 (%0.15) hem slipajı hem de borsa komisyonunu temsil eder.
    """
    kasa = baslangic_kasa
    btc_adet = 0.0
    ons_altin = 0.0
    
    # İlk günün dağılımına göre alım yapılıyor
    ilk_satir = d.iloc[0]
    btc_fiyat = ilk_satir["BTC"]
    altin_fiyat = ilk_satir["Altin"]
    
    if ilk_satir["Rejim"] == "🟢🟢 GÜÇLÜ BOĞA":
        kasa_harcama = kasa * (1 - komisyon_orani)
        btc_adet = kasa_harcama / btc_fiyat
        kasa = 0
    elif ilk_satir["Rejim"] == "🟡🟢 BOĞA + Kısa Düzeltme":
        kasa_harcama = kasa * 0.5 * (1 - komisyon_orani)
        btc_adet = kasa_harcama / btc_fiyat
        ons_altin = kasa_harcama / altin_fiyat
        kasa = 0
    else:
        kasa_harcama = kasa * (1 - komisyon_orani)
        ons_altin = kasa_harcama / altin_fiyat
        kasa = 0
        
    kasa_gecmisi = []
    onceki_rejim = ilk_satir["Rejim"]
    
    for idx, row in d.iterrows():
        mevcut_rejim = row["Rejim"]
        c_btc = row["BTC"]
        c_altin = row["Altin"]
        
        # Eğer rejim değiştiyse mevcut varlıklar nakde (kasa) döner, komisyon ödenir ve yeni dağılım alınır
        if mevcut_rejim != onceki_rejim:
            # Mevcutları sat ve kasaya dön (Satış Komisyonu)
            toplam_deger = (btc_adet * c_btc + ons_altin * c_altin) * (1 - komisyon_orani)
            btc_adet = 0.0
            ons_altin = 0.0
            
            # Yeni rejime göre paylaştır (Alış Komisyonu)
            if mevcut_rejim == "🟢🟢 GÜÇLÜ BOĞA":
                btc_adet = (toplam_deger * (1 - komisyon_orani)) / c_btc
            elif mevcut_rejim == "🟡🟢 BOĞA + Kısa Düzeltme":
                harcama = (toplam_deger * 0.5) * (1 - komisyon_orani)
                btc_adet = harcama / c_btc
                ons_altin = harcama / c_altin
            else:
                ons_altin = (toplam_deger * (1 - komisyon_orani)) / c_altin
                
            onceki_rejim = mevcut_rejim
            
        # Güncel portföy değerini hesapla
        guncel_deger = btc_adet * c_btc + ons_altin * c_altin + kasa
        kasa_gecmisi.append(guncel_deger)
        
    d["Portfoy"] = kasa_gecmisi
    d["Getiri"] = ((d["Portfoy"] - baslangic_kasa) / baslangic_kasa) * 100
    return d

# ── TELEGRAM ALARM SİSTEMİ ───────────────────────────────────────────────────
def telegram_gonder(mesaj):
    # Streamlit secrets kontrolü
    if "TELEGRAM_TOKEN" in st.secrets and "TELEGRAM_CHAT_ID" in st.secrets:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": chat_id, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
        except Exception:
            pass

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
            f"🚨 *LİKİDİTE REJİM DEĞİŞİKLİĞİ*\n"
            f"📅 Tarih: {tarih_str}\n"
            f"🔄 Geçiş: {state.get('son_rejim', 'BAŞLANGIÇ')} → {guncel_rejim}\n"
            f"📊 Önerilen Dağılım: {son_satir['Dagilim']}\n"
            f"💰 Güncel BTC: ${son_satir['BTC']:.2f}"
        )
        telegram_gonder(rapor)
        state["son_rejim"] = guncel_rejim
        with open(ALERT_STATE_FILE, "w") as f: json.dump(state, f)

if SCHEDULER_OK and "scheduler_calisiyor" not in st.session_state:
    scheduler = BackgroundScheduler()
    scheduler.add_job(anlik_kontrol_ve_alarm, 'interval', minutes=60)
    scheduler.start()
    st.session_state["scheduler_calisiyor"] = True

# ── ARAYÜZ VE GÖRSELLEŞTİRME ──────────────────────────────────────────────────
st.title("◆ Likidite Kompozit Paneli & Döngü Öncüsü")
st.caption("TradingView Tam Likidite Modeli ile Entegre Canlı İzleme ve Gerçekçi Komisyonlu Backtest")

df = veri_hazirla()

if not df.empty:
    # Gerçekçi Backtest Motorunu Çalıştır (%0.15 Maliyet/Kayma dahil)
    df = backtest_calistir(df)
    
    son = df.iloc[-1]
    
    # Metrik Alanları
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">GÜNCEL REJİM</div><div class="metric-value">{son["Rejim"]}</div></div>', unsafe_allowed_with_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">ÖNERİLEN DAĞILIM</div><div class="metric-value" style="font-size:1.2rem;">{son["Dagilim"]}</div></div>', unsafe_allowed_with_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">METAL RASYOSU (G/S+C)</div><div class="metric-value">{"✅ RISK-ON" if son["Risk_On"] else "❌ RISK-OFF"}</div></div>', unsafe_allowed_with_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">DXY DURUMU</div><div class="metric-value">{"✅ ZAYIF" if son["DXY_Zayif"] else "❌ GÜÇLÜ"}</div></div>', unsafe_allowed_with_html=True)
        
    # Grafik Alanı
    st.subheader("📈 Strateji Performansı vs Varlık Grafiği")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Portfoy"], name="Likidite Stratejisi (Maliyet Dahil)", line=dict(color="#00D2FF", width=2)))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=TEXT),
        xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # ── AI CO-PILOT (KORUMALI PROMPT ENTEGRASYONU) ────────────────────────────
    st.subheader("🤖 Makro Likidite Co-Pilot")
    soru = st.text_input("Sisteme veya güncel makro duruma dair bir soru sorun:")
    
    if soru and "GEMINI_API_KEY" in st.secrets:
        # Sistem Rolü (System Instruction) ekleyerek AI'ın tamamen stratejiye bağlı kalması sağlanıyor
        system_instruction = (
            "Sen 'Likidite Kompozit Modeli' için geliştirilmiş uzman bir finansal yapay zeka asistanısın. "
            "Kullanıcının sorularına sadece Metal Rasyosu, DXY, küresel likidite ve portföy rotasyonu "
            "cerçevesinde yanıt vermelisin. Yatırım tavsiyesi vermeden, eldeki verilere ve kurallara sadık kal."
        )
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={st.secrets['GEMINI_API_KEY']}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_instruction}\n\nGüncel Durum: Rejim={son['Rejim']}, Dağılım={son['Dagilim']}\nKullanıcı Sorusu: {soru}"}
                    ]
                }
            ]
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.ok:
                cevap = r.json()['candidates'][0]['content']['parts'][0]['text']
                st.info(cevap)
            else:
                st.error("AI modeline bağlanırken bir hata oluştu.")
        except Exception as e:
            st.error(f"Hata: {e}")
            
    # Geçmiş Tablo Dışa Aktarma
    st.subheader("📋 Son İşlem Geçmişi Durumu")
    degisimler = df[df["Rejim"] != df["Rejim"].shift(1)].tail(10)
    st.dataframe(degisimler[["Rejim", "Dagilim", "BTC", "Altin", "Portfoy", "Getiri"]])
