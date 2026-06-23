import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
from pathlib import Path
from datetime import datetime
import traceback

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    SCHEDULER_OK = True
except ImportError:
    SCHEDULER_OK = False

# ====================== SAYFA AYARI ======================
st.set_page_config(
    page_title="Likidite Kompozit Paneli",
    layout="wide",
    page_icon="◆",
    initial_sidebar_state="collapsed"
)

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

# ====================== PROFESYONEL CSS ======================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0A0C12; color: #E6E9EF; }

.lk-header { padding: 32px 0 24px 0; border-bottom: 1px solid #1E2533; margin-bottom: 28px; text-align: center; }
.lk-eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 0.15em; text-transform: uppercase; color: #6FE3B5; margin-bottom: 8px; }
.lk-title { font-size: 36px; font-weight: 700; color: #F2F4F8; letter-spacing: -0.02em; margin: 0; }
.lk-subtitle { font-size: 15.5px; color: #7C8595; max-width: 620px; margin: 12px auto 0; }

div[data-testid="stMetric"] {
    background: #131722; border: 1px solid #1E2533; border-radius: 14px; padding: 16px 18px;
}
div[data-testid="stMetric"] label { color: #7C8595 !important; font-size: 11.5px !important; text-transform: uppercase; letter-spacing: 0.05em; }
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-size: 22px !important; font-weight: 600; }

.lk-regime {
    border-radius: 14px; padding: 18px 24px; border: 1px solid; font-family: 'JetBrains Mono', monospace;
    font-weight: 700; font-size: 14.5px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
    margin: 8px 0 20px 0;
}
.lk-regime-strong-on { background: rgba(74,222,128,0.12); border-color: #4ADE80; color: #4ADE80; }
.lk-regime-weak-on { background: rgba(251,191,36,0.12); border-color: #FBBF24; color: #FBBF24; }
.lk-regime-weak-off { background: rgba(251,146,60,0.12); border-color: #FB923C; color: #FB923C; }
.lk-regime-strong-off { background: rgba(248,113,113,0.12); border-color: #F87171; color: #F87171; }

.lk-section {
    font-size: 16px; font-weight: 600; color: #F2F4F8; margin: 32px 0 14px 0;
    padding-left: 12px; border-left: 4px solid #6FE3B5;
}

.lk-ai-box {
    background: #131722; border: 1px solid #1E2533; border-radius: 14px;
    padding: 24px; line-height: 1.85; font-size: 15.2px; color: #C8CDD8;
}

.stButton > button {
    background: #1A202F; border: 1px solid #2A3140; color: #E6E9EF;
    border-radius: 10px; font-weight: 500; padding: 10px 20px;
}
.stButton > button:hover { border-color: #6FE3B5; color: #6FE3B5; }
</style>
""", unsafe_allow_html=True)

# ====================== BAŞLIK ======================
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD · HG=F · BTCUSD · 8 YILLIK ANALİZ</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">
        Altın · Bakır · Bitcoin üçlüsü üzerinden küresel likidite akışını ve rotasyon fırsatlarını izleyin
    </p>
</div>
""", unsafe_allow_html=True)

# ====================== SECRETS ======================
GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()
KONTROL_ARALIK = 15

# ====================== REJİM MOTORU ======================
def rejim_tespit(r, s10, s50):
    if r < s10 and r < s50:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢🟢 GÜÇLÜ BOĞA", 
                "Her iki sinyal BTC lehine · En güçlü likidite ortamı")
    elif r < s50:
        return ("Boğa + Düzeltme", 50, 50, "weak-on", "🟡🟢 BOĞA + DÜZELTME",
                "Uzun vade boğa · Kısa vadede konsolidasyon")
    elif r < s10:
        return ("Ayı + Toparlanma", 0, 100, "weak-off", "🟠🔴 AYI + TOPARLANMA",
                "Uzun vade ayı · Kısa vadede teknik rahatlama")
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴🔴 GÜÇLÜ AYI",
                "Her iki sinyal BTC aleyhine · Altın dominasyonu")

# ====================== YARDIMCI ======================
def fmt_pct(x): return f"%{x:+.1f}"
def fmt_usd(x): return f"${x:,.0f}"

def load_state():
    try:
        return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8")) if ALERT_STATE_FILE.exists() else {}
    except:
        return {}

def save_state(s):
    try:
        ALERT_STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except:
        pass

def telegram_gonder(mesaj):
    if not TOKEN or not CHAT_ID: return False
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
        return True
    except:
        return False

# ====================== GEMINI ======================
def gemini_api(prompt):
    if not GEMINI_KEY: return None
    models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if r.status_code == 429: continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except:
            continue
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def gemini_yorum_cache(btc_r, rejim, rot_k, bh_btc_k, bh_alt_k, kisa_bull, makro_bull):
    prompt = f"""
Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının anlayabileceği sade Türkçe ile 4-6 cümlelik özet yorum yaz.
Sonunda tek cümleyle "Şu an ne yapmalı?" önerisi ver.
- Bitcoin: ${btc_r:,.0f}
- Rejim: {rejim}
- Kısa vade: {"Boğa" if kisa_bull else "Ayı"}
- Uzun vade: {"Boğa" if makro_bull else "Ayı"}
- 8Y Rotasyon kazancı: {fmt_pct(rot_k)}
- BTC al-tut: {fmt_pct(bh_btc_k)}
- Altın al-tut: {fmt_pct(bh_alt_k)}
Sadece yorum metni yaz, başlık veya madde ekleme.
"""
    return gemini_api(prompt)

# ====================== VERİ & BACKTEST ======================
@st.cache_data(ttl=3600, show_spinner=False)
def verileri_getir():
    tickers = ["GC=F", "HG=F", "BTC-USD"]
    df = yf.download(tickers, period="8y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs('Close', axis=1, level=1)
    df = df.rename(columns={"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}).ffill().bfill()
    return df[["Altin", "Bakir", "Bitcoin"]]

@st.cache_data(ttl=3600, show_spinner=False)
def backtest_rotasyon(df):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d = d.dropna().copy()

    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows = []
    equity, btc_pct_list, alt_pct_list = [], [], []

    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        bp, ap = row["Bitcoin"], row["Altin"]
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(r, s10, s50)
        port_val = cash + btc_qty * bp + alt_qty * ap

        if prev_regime != isim:
            if isim == "Güçlü Boğa":
                btc_qty = port_val / bp; alt_qty = cash = 0.0
            elif isim == "Boğa + Düzeltme":
                btc_qty = (port_val * 0.5) / bp; alt_qty = (port_val * 0.5) / ap; cash = 0.0
            else:
                alt_qty = port_val / ap; btc_qty = cash = 0.0
            trade_rows.append({
                "Tarih": idx.strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'Başlangıç'} → {isim}",
                "Rejim": etiket,
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt}",
                "Portföy": round(port_val, 0),
            })
            prev_regime = isim

        port_now = cash + btc_qty * bp + alt_qty * ap
        equity.append(port_now)
        btc_pct_list.append(t_btc)
        alt_pct_list.append(t_alt)

    d["Portfoy"] = equity
    d["BtcPct"] = btc_pct_list
    d["AltinPct"] = alt_pct_list
    return d, pd.DataFrame(trade_rows), {"islem_sayisi": len(trade_rows), "toplam_gun": len(d)}

# ====================== SCHEDULER ======================
def rejim_kontrol_ve_bildir():
    try:
        df = yf.download(["GC=F", "HG=F", "BTC-USD"], period="60d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs('Close', axis=1, level=1)
        df = df.rename(columns={"GC=F":"Altin", "HG=F":"Bakir", "BTC-USD":"Bitcoin"}).ffill().bfill()
        if len(df) < 52: return

        df["Rasyo"] = df["Altin"] / (df["Bakir"] * df["Bitcoin"])
        df["SMA10"] = df["Rasyo"].rolling(10).mean()
        df["SMA50"] = df["Rasyo"].rolling(50).mean()
        last = df.iloc[-1]
        r, s10, s50 = float(last["Rasyo"]), float(last["SMA10"]), float(last["SMA50"])
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(r, s10, s50)

        state = load_state()
        prev = state.get("rejim", "")
        if prev and prev != etiket:
            mesaj = f"🚨 *REJİM DEĞİŞİMİ* 🚨\n\n{prev}\n⬇️\n*{etiket}*\n\nBTC: ${last['Bitcoin']:,.0f}\nPozisyon: BTC %{t_btc} · Altın %{t_alt}"
            telegram_gonder(mesaj)

        state.update({"rejim": etiket, "son_kontrol": datetime.now().strftime("%d.%m.%Y %H:%M"), "btc_fiyat": round(float(last["Bitcoin"]), 0)})
        save_state(state)
    except:
        pass

if SCHEDULER_OK and not st.session_state.get("scheduler_started", False):
    try:
        sch = BackgroundScheduler(timezone="Europe/Istanbul", daemon=True)
        sch.add_job(rejim_kontrol_ve_bildir, "interval", minutes=KONTROL_ARALIK, id="rejim_kontrol", replace_existing=True)
        sch.start()
        st.session_state["scheduler_started"] = True
    except:
        pass

# ====================== ANA UYGULAMA ======================
try:
    with st.spinner("8 yıllık veri yükleniyor ve analiz ediliyor..."):
        raw = verileri_getir()
        if raw.empty or len(raw) < 100:
            st.error("Yeterli veri çekilemedi.")
            st.stop()

        data, trade_log, stats = backtest_rotasyon(raw)
        last = data.iloc[-1]

        btc_fiyat = float(last["Bitcoin"])
        alt_fiyat = float(last["Altin"])
        son_rasyo = float(last["Rasyo"])
        sma10 = float(last["SMA10"])
        sma50 = float(last["SMA50"])

        kisa_bull = son_rasyo < sma10
        makro_bull = son_rasyo < sma50

        isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit(son_rasyo, sma10, sma50)

        data["BH_BTC"] = (10000 / data["Bitcoin"].iloc[0]) * data["Bitcoin"]
        data["BH_Altin"] = (10000 / data["Altin"].iloc[0]) * data["Altin"]

        rot_son = float(data["Portfoy"].iloc[-1])
        rot_kazanc = (rot_son / 10000 - 1) * 100
        bh_btc_k = (float(data["BH_BTC"].iloc[-1]) / 10000 - 1) * 100
        bh_alt_k = (float(data["BH_Altin"].iloc[-1]) / 10000 - 1) * 100

    # ==================== METRİKLER ====================
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin", fmt_usd(btc_fiyat), f"{(btc_fiyat/data['Bitcoin'].iloc[-2]-1)*100:+.1f}%")
    c2.metric("Altın", fmt_usd(alt_fiyat), f"{(alt_fiyat/data['Altin'].iloc[-2]-1)*100:+.1f}%")
    c3.metric("Rotasyon Portföy", fmt_usd(rot_son), fmt_pct(rot_kazanc))
    c4.metric("BTC Al-Tut", fmt_usd(data["BH_BTC"].iloc[-1]), fmt_pct(bh_btc_k))
    c5.metric("Altın Al-Tut", fmt_usd(data["BH_Altin"].iloc[-1]), fmt_pct(bh_alt_k))

    # ==================== REJİM BANNER ====================
    st.markdown(f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
        <span>{rejim_etiketi}</span>
        <span style="font-weight:400; font-size:13px; color:#9CA3AF">{rejim_aciklama}</span>
        <span style="margin-left:auto">BTC <b>%{btc_pct_now}</b> • Altın <b>%{alt_pct_now}</b></span>
    </div>
    """, unsafe_allow_html=True)

    # ==================== GRAFİKLER ====================
    tab1, tab2, tab3 = st.tabs(["Likidite Rasyosu", "Portföy Performansı", "Bakır/Altın + BTC"])

    with tab1:
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Altın/(Bakır×BTC)", line=dict(color="#7C8595")))
        fig1.add_trace(go.Scatter(x=data.index, y=data["SMA10"], name="SMA10", line=dict(color="#4ADE80", dash="dot")))
        fig1.add_trace(go.Scatter(x=data.index, y=data["SMA50"], name="SMA50", line=dict(color="#60A5FA")))
        fig1.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC Fiyatı", line=dict(color="#F0B90B"), yaxis="y2"))
        fig1.update_layout(height=520, template="plotly_dark", paper_bgcolor="#0A0C12", plot_bgcolor="#0A0C12")
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="Rotasyon Stratejisi", line=dict(color="#6FE3B5", width=3)))
        fig2.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="BTC Al-Tut", line=dict(color="#F0B90B", dash="dot")))
        fig2.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Altın Al-Tut", line=dict(color="#E5C07B", dash="dash")))
        fig2.update_layout(height=420, template="plotly_dark", paper_bgcolor="#0A0C12")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        data["Copper_Gold"] = data["Bakir"] / data["Altin"]
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        fig3.add_trace(go.Scatter(x=data.index, y=data["Copper_Gold"], name="Bakır/Altın", line=dict(color="#FB923C")))
        fig3.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC", line=dict(color="#F0B90B"), yaxis="y2"))
        fig3.update_layout(height=420, template="plotly_dark", paper_bgcolor="#0A0C12")
        st.plotly_chart(fig3, use_container_width=True)

    # ==================== İSTATİSTİKLER ====================
    st.markdown('<div class="lk-section">Strateji Performans İstatistikleri</div>', unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Toplam Rejim Geçişi", stats["islem_sayisi"])
    s2.metric("Maks. Portföy", fmt_usd(rot_son))
    s3.metric("Rotasyon Avantajı", fmt_usd(rot_son - float(data["BH_BTC"].iloc[-1])))
    s4.metric("İşlem Sıklığı", f"{stats['islem_sayisi']/8:.1f} geçiş/yıl")

    # ==================== İŞLEM GÜNLÜĞÜ ====================
    st.markdown('<div class="lk-section">8 Yıllık İşlem Günlüğü</div>', unsafe_allow_html=True)
    def renk_satir(row):
        if "Güçlü Boğa" in str(row.get("Geçiş", "")): return ["background-color: rgba(74,222,128,0.15)"] * len(row)
        elif "Boğa + Düzeltme" in str(row.get("Geçiş", "")): return ["background-color: rgba(251,191,36,0.12)"] * len(row)
        return [""] * len(row)
    
    st.dataframe(trade_log.style.apply(renk_satir, axis=1), use_container_width=True, hide_index=True)

    # ==================== ALARM SİSTEMİ ====================
    st.markdown('<div class="lk-section">Otomatik Alarm Sistemi · 7/24</div>', unsafe_allow_html=True)
    state = load_state()
    a1, a2, a3 = st.columns(3)
    a1.metric("Kontrol Sıklığı", f"Her {KONTROL_ARALIK} dakika", "✅ Aktif" if SCHEDULER_OK else "⚠️ Kapalı")
    a2.metric("Son Kontrol", state.get("son_kontrol", "—"))
    a3.metric("Mevcut Rejim", state.get("rejim", "—"))

    if st.button("📲 Güncel Durumu Telegram'a Gönder", type="primary"):
        rapor = f"◆ *LİKİDİTE KOMPOZİT PANELİ* ◆\n\n🪙 BTC: {fmt_usd(btc_fiyat)}\n🥇 Altın: {fmt_usd(alt_fiyat)}\n📊 Rejim: *{rejim_etiketi}*\n💼 Pozisyon: BTC %{btc_pct_now} · Altın %{alt_pct_now}\n📈 Rotasyon: {fmt_pct(rot_kazanc)}"
        if telegram_gonder(rapor):
            st.success("Telegram'a gönderildi!")
        else:
            st.error("Telegram gönderilemedi. Token kontrol edin.")

    # ==================== YAPAY ZEKA YORUMU ====================
    st.markdown('<div class="lk-section">Yapay Zeka Piyasa Yorumu</div>', unsafe_allow_html=True)
    if GEMINI_KEY:
        with st.spinner("Gemini analiz yapıyor..."):
            yorum = gemini_yorum_cache(
                round(btc_fiyat / 500) * 500, rejim_etiketi, rot_kazanc,
                bh_btc_k, bh_alt_k, kisa_bull, makro_bull
            )
        if yorum:
            st.markdown(f'<div class="lk-ai-box">{yorum}</div>', unsafe_allow_html=True)
        else:
            st.info("Yorum şu anda alınamadı (rate limit).")
    else:
        st.info("Gemini yorumu için secrets.toml dosyasına GEMINI_API_KEY ekleyin.")

    # Soru sorma
    soru = st.text_input("Strateji veya piyasa hakkında soru sorun:", placeholder="Örn: Şu anki rejimde ne yapmalıyım?")
    if soru and GEMINI_KEY:
        with st.spinner("Yanıt hazırlanıyor..."):
            yanit = gemini_api(f"""
Mevcut durum: {rejim_etiketi} | BTC: {fmt_usd(btc_fiyat)} | Pozisyon: BTC %{btc_pct_now}
8Y Rotasyon: {fmt_pct(rot_kazanc)} | BTC Al-Tut: {fmt_pct(bh_btc_k)}
Soru: {soru}
Sade Türkçe, kısa ve net cevap ver.
""")
            if yanit:
                st.markdown(f'<div class="lk-ai-box">{yanit}</div>', unsafe_allow_html=True)

except Exception as e:
    st.error("Bir hata oluştu")
    st.code(traceback.format_exc())
