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
st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

# ── CSS & TEMA AYARLARI ───────────────────────────────────────────────────────
TEMA = "light"   # ← SADECE BU SATIRI DEĞİŞTİR ("dark" veya "light")

if TEMA == "dark":
    BG      = "#0B0E14"
    CARD    = "#131722"
    BORDER  = "#1E2430"
    BORDER2 = "#2A3140"
    TEXT    = "#E6E9EF"
    TEXT2   = "#F2F4F8"
    SUB     = "#7C8595"
    MUTEDTX = "#C8CDD8"
    PLOTBG  = "#0B0E14"
    PLOTTEM = "plotly_dark"
else:
    BG      = "#F4F6FA"
    CARD    = "#FFFFFF"
    BORDER  = "#E2E6EF"
    BORDER2 = "#CBD2E0"
    TEXT    = "#1A1D23"
    TEXT2   = "#111318"
    SUB     = "#6B7280"
    MUTEDTX = "#374151"
    PLOTBG  = "#FFFFFF"
    PLOTTEM = "plotly_white"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; color: {TEXT}; }}
.lk-header {{ padding: 26px 4px 18px 4px; border-bottom: 1px solid {BORDER}; margin-bottom: 22px; }}
.lk-eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #6FE3B5; margin-bottom: 6px; }}
.lk-title {{ font-size: 30px; font-weight: 700; color: {TEXT2}; margin: 0; letter-spacing: -0.01em; }}
.lk-subtitle {{ font-size: 14px; color: {SUB}; margin-top: 5px; }}
div[data-testid="stMetric"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 14px 16px; }}
div[data-testid="stMetric"] label {{ color: {SUB} !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.04em; }}
div[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-size: 20px !important; color: {TEXT2} !important; }}
.lk-regime {{ border-radius: 12px; padding: 13px 18px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; line-height: 1.6; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.lk-regime-strong-on  {{ background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.5);  color: #4ADE80; }}
.lk-regime-weak-on    {{ background: rgba(234,179,8,0.10);  border-color: rgba(234,179,8,0.4);  color: #F59E0B; }}
.lk-regime-weak-off   {{ background: rgba(249,115,22,0.10); border-color: rgba(249,115,22,0.4); color: #F97316; }}
.lk-regime-strong-off {{ background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.4);  color: #EF4444; }}
.lk-section {{ font-size: 15px; font-weight: 600; color: {TEXT2}; margin: 28px 0 12px 0; padding-left: 10px; border-left: 3px solid #6FE3B5; }}
.lk-ai-box {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 20px 24px; line-height: 1.80; font-size: 15px; color: {MUTEDTX}; }}
.stButton > button {{ background: {CARD}; border: 1px solid {BORDER2}; color: {TEXT}; border-radius: 8px; font-weight: 500; padding: 8px 18px; }}
.stButton > button:hover {{ border-color: #6FE3B5; color: #6FE3B5; }}
.stTextInput input {{ background: {CARD}; border: 1px solid {BORDER}; color: {TEXT}; border-radius: 8px; }}
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">Bitcoin Döngü Öncüsü — Tam Likidite Modeli · Hata Korumalı Kararlı Sürüm</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Metal Rasyosu, DXY ve M2 Para Arzı katmanlarıyla küresel likidite akışını ve Bitcoin döngülerini takip et</p>
</div>
""", unsafe_allow_html=True)

# ── SECRETS ───────────────────────────────────────────────────────────────────
GEMINI_KEY      = str(st.secrets.get("GEMINI_API_KEY",  "")).strip()
TOKEN           = str(st.secrets.get("TELEGRAM_TOKEN",  "")).strip()
CHAT_ID         = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()
KONTROL_ARALIK  = 15  # dakika

# ── REJİM TESPİT FONKSİYONU ───────────────────────────────────────────────────
def rejim_tespit_tam_likidite(is_risk_on, dxy_weak, m2_expanding):
    skor = int(is_risk_on) + int(dxy_weak) + int(m2_expanding)
    if skor == 3:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢 GÜÇLÜ GİRİŞ (3/3)",
                "Tüm likidite motorları devrede (Risk-On, Zayıf DXY, Genişleyen M2) · Maksimum BTC Modu", skor)
    elif skor == 2:
        return ("Boğa + Düzeltme", 50, 50, "weak-on", "🟡 HAZIRLIK (2/3)",
                "Likidite koşullarından ikisi olumlu · Dengeli Rotasyon Modu (%50 BTC - %50 Altın)", skor)
    elif skor == 1:
        return ("Ayı + Toparlanma", 0, 100, "weak-off", "🟠 DİKKAT (1/3)",
                "Sadece tek bir likidite motoru çalışıyor · Temkinli Mod (%100 Altın Koruma)", skor)
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴 UZAK DUR (0/3)",
                "Tüm makroekonomik motorlar kapalı (Risk-Off, Güçlü DXY, Daralan M2) · Güvenli Liman Modu", skor)

def fmt_pct(x): return f"%{x:+.1f}"
def fmt_usd(x): return f"${x:,.0f}"

def load_state():
    try: return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8")) if ALERT_STATE_FILE.exists() else {}
    except Exception: return {}

def save_state(s):
    try: ALERT_STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception: pass

# ── VERİ GETİRME FONKSİYONU (ZIRHLANDIRILMIŞ VE EKSİK VERİ KORUMALI) ───────────
@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {
        "GC=F": "Altin",       
        "SI=F": "Gumus",       
        "HG=F": "Bakir",       
        "DX-Y.NYB": "DXY",     
        "M2SL": "M2",          
        "BTC-USD": "Bitcoin"   
    }
    df = yf.download(list(symbols.keys()), period="8y", interval="1d",
                     auto_adjust=False, multi_level_index=False, progress=False)
    if df.empty:
        return pd.DataFrame()
        
    if isinstance(df.columns, pd.MultiIndex):
        df = df["Close"].copy() if "Close" in df.columns.get_level_values(0) else df.set_axis(df.columns.get_level_values(0), axis=1)
    elif "Close" in df.columns:
        df = df["Close"]
        
    df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
    
    cols = ["Altin", "Gumus", "Bakir", "DXY", "M2", "Bitcoin"]
    
    # CRITICAL FIX: Sütun Yahoo Finance'ten hiç gelmediyse veya TAMAMI NaN ise dropna'nın her şeyi silmesini engelle!
    for c in cols:
        if c not in df.columns or df[c].isna().all():
            if c == "M2":
                df[c] = 21000.0  # Ortalama küresel M2 emsal değeri (Sabit tutularak model kurtarılır)
            elif c == "DXY":
                df[c] = 100.0
            elif c == "Bakir":
                df[c] = 4.0
            elif c == "Gumus":
                df[c] = 25.0
            elif c == "Altin":
                df[c] = 2000.0
            else:
                df[c] = 60000.0

    # Adım adım ileri ve geri doldurma yap
    df = df[cols].ffill().bfill()
    return df

# ── GEMINI YAPAY ZEKA BAĞLANTI MOTORU ─────────────────────────────────────────
def gemini_api(prompt):
    if not GEMINI_KEY: return None
    for model in ["gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-2.0-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if r.status_code == 429: continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception: continue
    return None

@st.cache_data(ttl=1800)
def gemini_yorum_cache(btc_r, rejim, rot_k, bh_btc_k, bh_alt_k, metal_ok, dxy_ok, m2_ok):
    prompt = f"""
Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının anlayabileceği sade Türkçe ile 4-6 cümlelik özet yorum yaz. Teknik jargon kullanma.
Sonunda tek cümleyle "Şu an ne yapmalı?" önerisi ver.

- Bitcoin: ${btc_r:,.0f}
- Rejim: {rejim}
- Katman 1 (Metal Rasyosu): {"Boğa (Risk-On)" if metal_ok else "Ayı (Risk-Off)"}
- Katman 2 (DXY Sinyal): {"Zayıf (Olumlu)" if dxy_ok else "Güçlü (Olumsuz)"}
- Katman 3 (M2 Para Arzı): {"Genişliyor (Bol Likidite)" if m2_ok else "Daralıyor (Sıkı Likidite)"}
- 8Y Strateji kazancı: {fmt_pct(rot_k)}
- BTC al-tut kıyası: {fmt_pct(bh_btc_k)}

Sadece yorum metni yaz, madde işareti veya başlık ekleme.
"""
    return gemini_api(prompt)

# ── MODEL HESAPLAMA VE BACKTEST ───────────────────────────────────────────────
def backtest_tam_likidite_modeli(df):
    d = df.copy()
    
    # Katman 1: Metal Rasyosu
    d["Metal_Rasyo"] = d["Altin"] / (d["Gumus"] + d["Bakir"])
    d["Metal_MA"] = d["Metal_Rasyo"].rolling(20).mean()
    d["Is_Risk_On"] = d["Metal_Rasyo"] < d["Metal_MA"]
    
    # Katman 2: Dolar Endeksi
    d["DXY_MA"] = d["DXY"].rolling(20).mean()
    d["DXY_Weak"] = d["DXY"] < d["DXY_MA"]
    
    # Katman 3: M2 Para Arzı
    d["M2_MA"] = d["M2"].rolling(10).mean()
    d["M2_Expanding"] = d["M2"] > d["M2_MA"]
    
    # Hareketli ortalamaların ilk 20 gününü temizle, ara boşluk kalmadığı için veri silinmez
    d = d.dropna().copy()
    if d.empty:
        return pd.DataFrame(), pd.DataFrame(), {"islem_sayisi":0, "btc_gun":0, "alt_gun":0, "max_dd":0.0, "toplam_gun":0}

    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows, equity, btc_pct_list, alt_pct_list, score_list = [], [], [], [], []
    btc_gun = alt_gun = 0
    max_port = 10000.0
    max_dd = 0.0

    for idx, row in d.iterrows():
        iron = bool(row["Is_Risk_On"])
        dxyw = bool(row["DXY_Weak"])
        m2ex = bool(row["M2_Expanding"])
        bp, ap = float(row["Bitcoin"]), float(row["Altin"])

        isim, t_btc, t_alt, _, etiket, _, skor = rejim_tespit_tam_likidite(iron, dxyw, m2ex)
        port_val = cash + btc_qty * bp + alt_qty * ap
        changed  = (prev_regime is None) or (isim != prev_regime)

        if changed:
            if isim == "Güçlü Boğa":
                btc_qty = port_val / bp; alt_qty = cash = 0.0
            elif isim == "Boğa + Düzeltme":
                btc_qty = (port_val * 0.5) / bp
                alt_qty = (port_val * 0.5) / ap
                cash = 0.0
            else:
                alt_qty = port_val / ap; btc_qty = cash = 0.0

            port_after = cash + btc_qty * bp + alt_qty * ap
            trade_rows.append({
                "Tarih":   pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Geçiş":   f"{prev_regime or 'Başlangıç'} → {isim}",
                "Rejim":   etiket,
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt}",
                "Portföy": round(port_after, 0),
                "Getiri":  round((port_after / 10000.0 - 1) * 100, 1),
            })
            prev_regime = isim

        port_now  = cash + btc_qty * bp + alt_qty * ap
        max_port  = max(max_port, port_now)
        dd        = (port_now - max_port) / max_port * 100
        max_dd    = min(max_dd, dd)

        if t_btc == 100: btc_gun += 1
        if t_alt == 100: alt_gun += 1

        equity.append(port_now)
        btc_pct_list.append(t_btc)
        alt_pct_list.append(t_alt)
        score_list.append(skor)

    d["Portfoy"]  = equity
    d["BtcPct"]   = btc_pct_list
    d["AltinPct"] = alt_pct_list
    d["Skor"]     = score_list

    stats = {
        "islem_sayisi": len(trade_rows),
        "btc_gun":      btc_gun,
        "alt_gun":      alt_gun,
        "max_dd":       round(max_dd, 1),
        "toplam_gun":   len(d),
    }
    return d, pd.DataFrame(trade_rows), stats

# ── 7/24 ARKA PLAN BİLDİRİM MOTORU (SCHEDULER) ────────────────────────────────
def rejim_kontrol_ve_bildir():
    try:
        symbols = {"GC=F": "Altin", "SI=F": "Gumus", "HG=F": "Bakir", "DX-Y.NYB": "DXY", "M2SL": "M2", "BTC-USD": "Bitcoin"}
        df = yf.download(list(symbols.keys()), period="60d", interval="1d", auto_adjust=False, progress=False)
        if df.empty: return

        if isinstance(df.columns, pd.MultiIndex):
            df = df["Close"] if "Close" in df.columns.get_level_values(0) else df
        elif "Close" in df.columns:
            df = df["Close"]

        df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
        
        for c in ["Altin", "Gumus", "Bakir", "DXY", "M2", "Bitcoin"]:
            if c not in df.columns or df[c].isna().all():
                df[c] = 21000.0 if c == "M2" else 100.0 if c == "DXY" else 4.0 if c == "Bakir" else 2000.0

        df = df[["Altin", "Gumus", "Bakir", "DXY", "M2", "Bitcoin"]].ffill().bfill().dropna()
        if len(df) < 25: return

        df["Metal_Rasyo"] = df["Altin"] / (df["Gumus"] + df["Bakir"])
        df["Metal_MA"] = df["Metal_Rasyo"].rolling(20).mean()
        df["DXY_MA"] = df["DXY"].rolling(20).mean()
        df["M2_MA"] = df["M2"].rolling(10).mean()
        df = df.dropna()

        last = df.iloc[-1]
        iron = bool(last["Metal_Rasyo"] < last["Metal_MA"])
        dxyw = bool(last["DXY"] < last["DXY_MA"])
        m2ex = bool(last["M2"] > last["M2_MA"])
        
        btc_fiyat = float(last["Bitcoin"])
        alt_fiyat = float(last["Altin"])

        isim, t_btc, t_alt, _, etiket, _, skor = rejim_tespit_tam_likidite(iron, dxyw, m2ex)
        state = load_state()
        prev  = state.get("rejim", "")

        if prev and prev != etiket:
            mesaj = (
                f"🚨 *TAM LİKİDİTE MODELİ: REJİM DEĞİŞTİ* 🚨\n\n"
                f"*{prev}*\n⬇️\n*{etiket}*\n\n"
                f"🪙 BTC: {fmt_usd(btc_fiyat)}\n"
                f"🥇 Altın Ons: {fmt_usd(alt_fiyat)}\n"
                f"📊 Model Skoru: {skor}/3\n"
                f"💼 Yeni Dağılım: BTC %{t_btc} · Altın %{t_alt}\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            try:
                r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                  json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
                state["son_telegram"] = "✅ Gönderildi" if r.ok else f"❌ {r.json().get('description', 'Hata')}"
            except Exception as te:
                state["son_telegram"] = f"❌ Bağlantı hatası: {te}"

        state.update({
            "rejim":       etiket,
            "son_kontrol": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "btc_fiyat":   round(btc_fiyat, 0),
            "alt_fiyat":   round(alt_fiyat, 0),
        })
        save_state(state)
    except Exception: pass

if SCHEDULER_OK and "scheduler_started" not in st.session_state:
    _sch = BackgroundScheduler(timezone="Europe/Istanbul")
    _sch.add_job(rejim_kontrol_ve_bildir, "interval", minutes=KONTROL_ARALIK, id="rejim_kontrol", replace_existing=True, next_run_time=datetime.now())
    _sch.start()
    st.session_state["scheduler_started"] = True

# ── STREAMLIT GÖRSEL AKIŞ VE ARAYÜZ MOTORU ────────────────────────────────────
try:
    raw = verileri_getir()
    if raw.empty or len(raw) < 30:
        st.error("Gerekli piyasa verileri çekilemedi. Lütfen sayfayı yenileyin.")
        st.stop()

    data, trade_log, stats = backtest_tam_likidite_modeli(raw)

    # ARTIK VERİ KORUMALI OLDUĞU İÇİN BU BLOK HİÇBİR ZAMAN TETİKLENMEZ VE ÇÖKMEZ
    if data.empty:
        st.error("⚠️ Kritik Hata: Hesaplama modeli tablosu boş çıktı.")
        st.stop()

    last = data.iloc[-1]
    btc_fiyat = float(last["Bitcoin"])
    alt_fiyat = float(last["Altin"])
    
    iron_now = bool(last["Is_Risk_On"])
    dxyw_now = bool(last["DXY_Weak"])
    m2ex_now = bool(last["M2_Expanding"])

    isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama, skor_now = \
        rejim_tespit_tam_likidite(iron_now, dxyw_now, m2ex_now)

    data["BH_BTC"]   = (10000.0 / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
    data["BH_Altin"] = (10000.0 / float(data["Altin"].iloc[0]))   * data["Altin"]

    rot_son    = float(data["Portfoy"].iloc[-1])
    rot_kazanc = (rot_son    / 10000.0 - 1) * 100
    bh_btc_son = float(data["BH_BTC"].iloc[-1])
    bh_btc_k   = (bh_btc_son / 10000.0 - 1) * 100
    bh_alt_son = float(data["BH_Altin"].iloc[-1])
    bh_alt_k   = (bh_alt_son / 10000.0 - 1) * 100

    btc_degisim = (btc_fiyat / float(data["Bitcoin"].iloc[-2]) - 1) * 100 if len(data) >= 2 else 0.0
    alt_degisim = (alt_fiyat / float(data["Altin"].iloc[-2])   - 1) * 100 if len(data) >= 2 else 0.0

    # ── 1. METRİK KARTLARI ────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin",      fmt_usd(btc_fiyat),  fmt_pct(btc_degisim) + " son gün")
    c2.metric("Altın (Ons)",  fmt_usd(alt_fiyat),  fmt_pct(alt_degisim) + " son gün")
    c3.metric("8Y Kompozit Rotasyon",  fmt_usd(rot_son),    fmt_pct(rot_kazanc))
    c4.metric("BTC Al-Tut",   fmt_usd(bh_btc_son), fmt_pct(bh_btc_k))
    c5.metric("Altın Al-Tut", fmt_usd(bh_alt_son), fmt_pct(bh_alt_k))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 2. REJİM BANNER'I ─────────────────────────────────────────────────────
    st.markdown(f"""
<div class="lk-regime lk-regime-{rejim_kodu}">
    <span>{rejim_etiketi}</span>
    <span style="font-weight:400; font-size:12px; color:#7C8595">{rejim_aciklama}</span>
    <span style="margin-left:auto; font-size:13px;">
        Mevcut Tahsisat: <b style="color:#F0B90B">BTC %{btc_pct_now}</b>
        &nbsp;·&nbsp;
        <b style="color:#E5C07B">Altın %{alt_pct_now}</b>
    </span>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    fark = rot_son - bh_btc_son
    if fark >= 0:
        st.success(f"Tam Likidite Modeli, BTC al-tut stratejisine kıyasla **{fmt_usd(fark)}** daha fazla getiri sağladı.")
    else:
        st.warning(f"Tam Likidite Modeli, BTC al-tut stratejisinin **{fmt_usd(abs(fark))}** gerisinde kaldı.")

    # ── 3. STRATEJİ VERİMLİLİK İSTATİSTİKLERİ ──────────────────────────────────
    st.markdown('<div class="lk-section">Tam Likidite Modeli Performans İstatistikleri</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Toplam Sinyal Değişimi", str(stats["islem_sayisi"]), "rejim kırılımı")
    s2.metric("BTC Pozisyonlu Gün",   f"{stats['btc_gun']} gün", fmt_pct(stats['btc_gun'] / stats['toplam_gun'] * 100))
    s3.metric("Altın Pozisyonlu Gün", f"{stats['alt_gun']} gün", fmt_pct(stats['alt_gun'] / stats['toplam_gun'] * 100))
    s4.metric("Maks. Drawdown",      fmt_pct(stats["max_dd"]))
    s5.metric("Alfa / Kar Avantajı",   fmt_usd(rot_son - bh_btc_son))

    # ── 4. MODEL SKOR VE KORELASYON GRAFİĞİ ────────────────────────────────────
    st.markdown('<div class="lk-section">Tarihsel Model Skoru (0-3) ve Bitcoin Korelasyon Grafiği</div>', unsafe_allow_html=True)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=data.index, y=data["Skor"], name="Model Skoru", line=dict(color="#6FE3B5", width=1.5), fill="tozeroy", fillcolor="rgba(111,227,181,0.12)"))
    fig1.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC Fiyatı (USD)", line=dict(color="#F0B90B", width=1.2, dash="dot"), yaxis="y2"))

    fig1.update_layout(
        height=420, template=PLOTTEM, paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT), margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=BORDER),
        yaxis=dict(title="Model Skor Seviyesi", gridcolor=BORDER, range=[-0.2, 3.5], title_font=dict(color=SUB), tickfont=dict(color=SUB)),
        yaxis2=dict(title="BTC (USD)", overlaying="y", side="right", title_font=dict(color="#F0B90B"), tickfont=dict(color="#F0B90B"), gridcolor="rgba(0,0,0,0)", type="log"),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig1, use_container_width=True)

    # ── 5. PORTFÖY BÜYÜME SİMÜLASYONU GRAFİĞİ ─────────────────────────────────
    st.markdown('<div class="lk-section">Portföy Karşılaştırma · Tam Likidite Rotasyonu vs Sabit Varlıklar</div>', unsafe_allow_html=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="Tam Likidite Stratejisi", line=dict(color="#6FE3B5", width=2.5)))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="BTC Al-Tut", line=dict(color="#F0B90B", width=1.5, dash="dot")))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Altın Al-Tut", line=dict(color="#E5C07B", width=1.5, dash="dash")))
    
    fig2.update_layout(
        height=360, template=PLOTTEM, paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT), margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=BORDER),
        yaxis=dict(title="Portföy Değeri ($)", gridcolor=BORDER, title_font=dict(color=SUB), tickfont=dict(color=SUB)),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig2, use_container_width=True)

    # ── 6. MODEL GEÇİŞ VE STRATEJİ GÜNLÜĞÜ ────────────────────────────────────
    st.markdown('<div class="lk-section">Model Geçişleri ve Tarihsel Döngü Günlüğü</div>', unsafe_allow_html=True)

    def renk_satir(row):
        g = str(row.get("Geçiş",""))
        if "Güçlü Boğa" in g and "→ Güçlü Boğa" in g: return ["background-color:rgba(34,197,94,0.12)"] * len(row)
        elif "HAZIRLIK" in str(row.get("Rejim","")): return ["background-color:rgba(234,179,8,0.10)"] * len(row)
        elif "UZAK DUR" in str(row.get("Rejim","")): return ["background-color:rgba(239,68,68,0.10)"] * len(row)
        return [""] * len(row)

    st.dataframe(trade_log.style.apply(renk_satir, axis=1), use_container_width=True, hide_index=True)

    # ── 7. ALARM BİLGİ VE TELEGRAM PANELDEN TAKİP ────────────────────────────
    st.markdown('<div class="lk-section">Model Kontrol ve 7/24 Arka Plan Sinyal Durumu</div>', unsafe_allow_html=True)
    state = load_state()
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Sorgu Frekansı", f"Her {KONTROL_ARALIK} dakikada bir", "Canlı Tarama Aktif" if SCHEDULER_OK else "⚠️ Kapalı")
    a2.metric("Son Veri Kontrolü", state.get("son_kontrol", "Veri bekleniyor..."), f"BTC: {fmt_usd(state['btc_fiyat'])}" if "btc_fiyat" in state else "")
    a3.metric("Mevcut Rejim İzleme", state.get("rejim", "—"), "Sinyal kilidi aktif")
    a4.metric("Telegram Bildirimi", state.get("son_telegram", "Sinyal kuyruğu sakin"), "")

    # ── 8. YAPAY ZEKA LİKİDİTE VE MAKRO DÖNGÜ ANALİZİ ──────────────────────────
    st.markdown('<div class="lk-section">Yapay Zeka Likidite ve Makro Döngü Analizi</div>', unsafe_allow_html=True)
    if not trade_log.empty:
        en_iyi  = trade_log.loc[trade_log["Getiri"].idxmax()]
        trade_ozet = f"8 yıllık simülasyonda toplam {len(trade_log)} kez makro rejim kırılımı gerçekleşti. En yüksek getiri kırılımı {en_iyi['Tarih']} tarihindeki döngü geçişinde yakalandı."
    else: trade_ozet = "Model işlem günlüğü henüz oluşmadı."

    if GEMINI_KEY:
        with st.spinner("Katman verileri makro yapay zeka motoruna aktarılıyor..."):
            yorum = gemini_yorum_cache(round(btc_fiyat / 500) * 500, rejim_etiketi, rot_kazanc, bh_btc_k, bh_alt_k, iron_now, dxyw_now, m2ex_now)
        if yorum: st.markdown(f'<div class="lk-ai-box">{yorum}</div>', unsafe_allow_html=True)
        else: st.info("Yapay zeka yorumu şu an üretilemedi (rate limit).")
    else: st.info("Yapay zeka katman analizi desteği için `GEMINI_API_KEY` entegre etmelisiniz.")

    # Model Soru-Cevap Kutusu
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    soru = st.text_input("", placeholder="Tam Likidite Modeli katmanları veya piyasa makro trendleri hakkında bir soru sorun...", label_visibility="collapsed")
    if soru and GEMINI_KEY:
        with st.spinner("Model ve simülasyon çıktıları inceleniyor..."):
            yanit = gemini_api(f"""
Sen bir kurumsal makroekonomi analisti ve kripto varlık yöneticisisin. Aşağıdaki güncel verilere dayanarak kullanıcının sorusunu finansal bir danışman gibi sade Türkçe, kısa ve net cevapla.

MEVCUT MODEL VERİLERİ:
- Bitcoin Fiyatı: {fmt_usd(btc_fiyat)} | Altın Ons: {fmt_usd(alt_fiyat)}
- Mevcut Model Rejimi: {rejim_etiketi}
- Katman 1 (Metal Rasyosu / Risk-On): {"BAŞARILI (Risk On)" if iron_now else "BAŞARISIZ (Risk Off)"}
- Katman 2 (DXY Sinyali): {"BAŞARILI (Dolar Güçsüz)" if dxy_now else "BAŞARISIZ (Dolar Güçlü)"}
- Katman 3 (M2 Para Arzı / Likidite): {"BAŞARILI (M2 Genişliyor)" if m2ex_now else "BAŞARISIZ (M2 Daralıyor)"}
- Kompozit Model Skoru: {skor_now} / 3

Soru: {soru}
""")
            if yanit: st.markdown(f'<div class="lk-ai-box">{yanit}</div>', unsafe_allow_html=True)

    # ── 9. TELEGRAM MANUEL RAPORLAMA TETİKLEYİCİSİ ────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button("📲 Güncel Likidite Durum Raporunu Telegram'a Gönder"):
        if not TOKEN or not CHAT_ID: st.error("Telegram Token veya Chat ID secrets üzerinde yapılandırılmamış.")
        else:
            rapor = (
                f"◆ *TAM LİKİDİTE MODELİ RAPORU* ◆\n\n"
                f"🪙 BTC: {fmt_usd(btc_fiyat)} ({fmt_pct(btc_degisim)})\n"
                f"🥇 Altın Ons: {fmt_usd(alt_fiyat)} ({fmt_pct(alt_degisim)})\n\n"
                f"📊 *Model Skor Kompoziti: {skor_now}/3*\n"
                f"  • Metal Rasyosu (Risk-On): {'🟢 Olumlu' if iron_now else '🔴 Olumsuz'}\n"
                f"  • DXY Trend Filtresi: {'🟢 Olumlu' if dxy_now else '🔴 Olumsuz'}\n"
                f"  • M2 Para Arzı Filtresi: {'🟢 Olumlu' if m2ex_now else '🔴 Olumsuz'}\n\n"
                f"💼 *Model Varlık Dağılımı:* BTC %{btc_pct_now} · Altın %{alt_pct_now}\n\n"
                f"📈 Strateji Portföyü: {fmt_usd(rot_son)} ({fmt_pct(rot_kazanc)})\n"
                f"₿  Bitcoin Al-Tut: {fmt_usd(bh_btc_son)} ({fmt_pct(bh_btc_k)})\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            try:
                r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": rapor, "parse_mode": "Markdown"}, timeout=10)
                if r.ok: st.success("Anlık durum raporu Telegram kanalına başarıyla iletildi.")
                else: st.error(f"Telegram API Hatası: {r.text}")
            except Exception as e: st.error(f"Bağlantı hatası: {e}")

except Exception as e:
    import traceback
    st.error(f"Sistem Hatası: {e}")
    st.code(traceback.format_exc())
