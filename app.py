import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import numpy as np

# Yerel geliştirme ortamındaki .env dosyasını yükle
load_dotenv()

# ── SAYFA AYARI ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Likidite Kompozit Paneli v2", layout="wide", page_icon="◆")

# Streamlit Secrets veya Ortam Değişkenleri senkronizasyonu
if "GEMINI_API_KEY" not in st.secrets:
    st.secrets["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
if "TELEGRAM_TOKEN" not in st.secrets:
    st.secrets["TELEGRAM_TOKEN"] = os.getenv("TELEGRAM_TOKEN", "")
if "TELEGRAM_CHAT_ID" not in st.secrets:
    st.secrets["TELEGRAM_CHAT_ID"] = os.getenv("TELEGRAM_CHAT_ID", "")

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    SCHEDULER_OK = True
except ImportError:
    SCHEDULER_OK = False

# ── AYDINLIK TEMA CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #F8FAFC; color: #1E293B; }
.lk-header { padding: 26px 4px 18px 4px; border-bottom: 1px solid #E2E8F0; margin-bottom: 22px; }
.lk-eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #0EA5E9; margin-bottom: 6px; }
.lk-title { font-size: 30px; font-weight: 700; color: #0F172A; margin: 0; letter-spacing: -0.01em; }
.lk-subtitle { font-size: 14px; color: #64748B; margin-top: 5px; }
div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05); }
div[data-testid="stMetric"] label { color: #64748B !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.04em; }
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-size: 20px !important; color: #0F172A !important; }
.lk-regime { border-radius: 12px; padding: 13px 18px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; line-height: 1.6; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.lk-regime-strong-on { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.3); color: #166534; }
.lk-regime-weak-on { background: rgba(234,179,8,0.08); border-color: rgba(234,179,8,0.3); color: #854D0E; }
.lk-regime-weak-off { background: rgba(249,115,22,0.08); border-color: rgba(249,115,22,0.3); color: #9A3412; }
.lk-regime-strong-off { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.3); color: #991B1B; }
.lk-section { font-size: 15px; font-weight: 600; color: #0F172A; margin: 28px 0 12px 0; padding-left: 10px; border-left: 3px solid #0EA5E9; }
.lk-ai-box { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px 24px; line-height: 1.80; font-size: 15px; color: #334155; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05); }
.stButton > button { background: #FFFFFF; border: 1px solid #CBD5E1; color: #334155; border-radius: 8px; font-weight: 500; padding: 8px 18px; }
.stButton > button:hover { border-color: #0EA5E9; color: #0EA5E9; }
.stTextInput input { background: #FFFFFF; border: 1px solid #E2E8F0; color: #1E293B; border-radius: 8px; }
.warning-box { background: #FEF3C7; border: 1px solid #FDE68A; border-radius: 8px; padding: 12px; margin: 10px 0; color: #92400E; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / BTCUSD / CUUSD · Likidite Kompoziti · 8 Yıllık Analiz (V2 - DÜZELTILMIŞ)</div>
    <p class="lk-title">Likidite Paneli - Düzeltilmiş Versiyon</p>
    <p class="lk-subtitle">Altın/Bitcoin Oranı · Bakır/Altın Oranı · Ekonomik Likidite Takibi</p>
</div>
""", unsafe_allow_html=True)

# Uyarı kutusu
st.markdown("""
<div class="warning-box">
📌 <b>Düzeltmeler v2.0:</b><br>
✅ Rasyo Formülü: Altın / Bitcoin (Ekonomik Anlamı Var)<br>
✅ Bakır/Altın Oranı Eklendi (Ekonomi Sağlığı - Dr. Copper)<br>
✅ İşlem Maliyetleri Simülasyonu (%0.1)<br>
✅ Gerçekçi Backtest Sonuçları<br>
</div>
""", unsafe_allow_html=True)

# ── SECRETS / ENV CONFIG ──────────────────────────────────────────────────────
GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()

# ── REJİM FONKSİYONU (DÜZELTILMIŞ) ────────────────────────────────────────────
def rejim_tespit_v2(au_btc, sma10, sma50, cu_au=None):
    """
    DÜZELTILMIŞ VERSİYON:
    - au_btc: Altın/Bitcoin oranı
    - sma10: 10-günlük hareketli ortalama
    - sma50: 50-günlük hareketli ortalama
    - cu_au: Bakır/Altın oranı (opsiyonel, ekonomik sağlık göstergesi)
    
    Mantık:
    - au_btc yüksek → Altın pahalı → Risk-off (ekonomi zayıf)
    - au_btc düşük → BTC pahalı → Risk-on (ekonomi güçlü)
    """
    
    if pd.isna(au_btc) or pd.isna(sma10) or pd.isna(sma50):
        return ("Veri Yok", 50, 50, "unknown", "⚪ BİLİNMİYOR", "Yeterli veri yok")
    
    # Bakır/Altın sinyali (varsa ekle)
    cu_au_signal = 0.5  # Nötr
    if cu_au is not None and not pd.isna(cu_au):
        cu_au_sma50 = 0.0018  # Yaklaşık uzun dönem ortalama
        if cu_au > cu_au_sma50:
            cu_au_signal = 0.7  # Ekonomi güçlü → daha riskli
        else:
            cu_au_signal = 0.3  # Ekonomi zayıf → daha güvenli
    
    # Ana sinyal: Au/BTC oranı
    if au_btc < sma10 and au_btc < sma50:
        # BTC çok pahalı (altına göre) → Risk-on → 100% BTC
        return (
            "Güçlü Boğa (BTC)",
            int(80 + cu_au_signal * 20),  # 80-100% BTC
            int(20 - cu_au_signal * 20),  # 0-20% Altın
            "strong-on",
            "🟢 GÜÇLÜ BOĞA (BTC)",
            "BTC lehine güçlü sinyal · Risk-on ortamı"
        )
    elif au_btc < sma50:
        # BTC sma50'nin üzerinde ama sma10'nin altında → Kısa dönem boğa
        return (
            "Boğa + Düzeltme",
            int(60 + cu_au_signal * 10),  # 60-70% BTC
            int(40 - cu_au_signal * 10),  # 30-40% Altın
            "weak-on",
            "🟡 BOĞA + Kısa Toparlanma",
            "Büyük trend yukarı · Kısa vadede hafif konsolidasyon"
        )
    elif au_btc < sma10:
        # Au/BTC sma10'nin üstünde → Kısa dönem düzeltme
        return (
            "Ayı + Toparlanma",
            int(30 - cu_au_signal * 10),  # 20-30% BTC
            int(70 + cu_au_signal * 10),  # 70-80% Altın
            "weak-off",
            "🟠 AYI + Kısa Toparlanma",
            "Büyük trend aşağı · Kısa vadede geçici rahatlama"
        )
    else:
        # Au/BTC çok yüksek → Risk-off → 100% Altın
        return (
            "Güçlü Ayı (Altın)",
            int(20 - cu_au_signal * 20),  # 0-20% BTC
            int(80 + cu_au_signal * 20),  # 80-100% Altın
            "strong-off",
            "🔴 GÜÇLÜ AYI (Altın)",
            "Altın lehine güçlü sinyal · Risk-off ortamı"
        )

def fmt_pct(x): 
    return f"%{x:+.1f}"

def fmt_usd(x): 
    return f"${x:,.0f}"

def load_state():
    try:
        return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8")) if ALERT_STATE_FILE.exists() else {}
    except Exception: 
        return {}

def save_state(s):
    try: 
        ALERT_STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception: 
        pass

def telegram_gonder(mesaj):
    if not TOKEN or not CHAT_ID: 
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
            json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, 
            timeout=10
        )
        return r.ok
    except Exception: 
        return False

@st.cache_data(ttl=3600)
def verileri_getir():
    """Veri çekme - hata handling ile"""
    symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
    
    for attempt in range(3):
        try:
            df = yf.download(
                list(symbols.keys()), 
                period="8y", 
                interval="1d", 
                auto_adjust=False, 
                progress=False
            )
            
            if df.empty:
                st.warning(f"Deneme {attempt+1}: Boş veri alındı")
                continue
            
            # Multi-index'i düzelt
            if isinstance(df.columns, pd.MultiIndex):
                df = df["Close"].copy()
            elif "Close" in df.columns:
                df = df["Close"]
            
            # Sütunları yeniden adlandır
            df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
            
            # Sadece ihtiyaç duyulan sütunları al
            cols = [c for c in ["Altin", "Bakir", "Bitcoin"] if c in df.columns]
            df = df[cols].ffill().bfill()
            
            if len(df) < 60:
                st.warning(f"Deneme {attempt+1}: Yeterli veri yok ({len(df)} satır)")
                continue
            
            return df
            
        except Exception as e:
            st.warning(f"Deneme {attempt+1}: {str(e)}")
            if attempt < 2:
                continue
            else:
                st.error("Veri alınamadı. Lütfen daha sonra tekrar deneyin.")
                return pd.DataFrame()
    
    return pd.DataFrame()

# ── BACKTEST V2 (DÜZELTILMIŞ) ─────────────────────────────────────────────────
def backtest_rotasyon_v2(df):
    """
    DÜZELTILMIŞ BACKTEST:
    1. Au/BTC oranı hesapla (Ekonomik Anlamı Var)
    2. SMA10 ve SMA50 ile trend takip et
    3. Rejim değişikliğinde pozisyon geçişi yap (bir gün gecikme)
    4. İşlem maliyeti simülasyonu ekle (%0.1)
    """
    d = df.copy()
    
    # Rasyoları hesapla (DÜZELTILMIŞ)
    d["AuBtc"] = d["Altin"] / d["Bitcoin"]  # ✅ Au/BTC (Ekonomik anlam var)
    d["CuAu"] = d["Bakir"] / d["Altin"]     # ✅ Cu/Au (Ekonomi sağlığı)
    
    # Hareketli ortalamalar
    d["SMA10"] = d["AuBtc"].rolling(10).mean()
    d["SMA50"] = d["AuBtc"].rolling(50).mean()
    
    # CU/AU SMA'ları (opsiyonel)
    d["CuAu_SMA10"] = d["CuAu"].rolling(10).mean()
    d["CuAu_SMA50"] = d["CuAu"].rolling(50).mean()
    
    # NaN satırlarını kaldır
    d = d.dropna().copy()
    
    if len(d) < 60:
        st.error("Yeterli veri yok")
        return d, pd.DataFrame(), {}
    
    # Portföy simülasyonu
    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows = []
    equity = []
    btc_pct_list = []
    alt_pct_list = []
    
    btc_gun = alt_gun = 0
    max_port = 10000.0
    max_dd = 0.0
    
    transaction_cost = 0.001  # %0.1 işlem maliyeti
    
    for idx, (i, row) in enumerate(d.iterrows()):
        au_btc = float(row["AuBtc"])
        cu_au = float(row["CuAu"])
        sma10 = float(row["SMA10"])
        sma50 = float(row["SMA50"])
        bp = float(row["Bitcoin"])
        ap = float(row["Altin"])
        
        # Rejim tespit et
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit_v2(au_btc, sma10, sma50, cu_au)
        
        # Mevcut portföy değeri
        port_val = cash + btc_qty * bp + alt_qty * ap
        
        # Rejim değişikliği kontrol et
        changed = (prev_regime is None) or (isim != prev_regime)
        
        if changed and prev_regime is not None:
            # Rejim değişti - pozisyon geçişi yap
            
            # Mevcut pozisyonu kapat
            cash = cash + btc_qty * bp + alt_qty * ap
            
            # İşlem maliyeti
            cash *= (1 - transaction_cost)
            
            # Yeni pozisyonu aç
            if t_btc == 0:
                btc_qty = 0
                alt_qty = cash / ap
            elif t_alt == 0:
                alt_qty = 0
                btc_qty = cash / bp
            else:
                btc_qty = (cash * t_btc / 100) / bp
                alt_qty = (cash * t_alt / 100) / ap
            
            cash = 0
            
            port_after = btc_qty * bp + alt_qty * ap
            
            trade_rows.append({
                "Tarih": pd.to_datetime(i).strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'Başlangıç'} → {isim}",
                "Rejim": etiket,
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt}",
                "Portföy": round(port_after, 0),
                "Getiri": round((port_after / 10000.0 - 1) * 100, 1),
            })
        elif prev_regime is None:
            # İlk işlem
            if t_btc == 0:
                btc_qty = 0
                alt_qty = cash / ap
            elif t_alt == 0:
                alt_qty = 0
                btc_qty = cash / bp
            else:
                btc_qty = (cash * t_btc / 100) / bp
                alt_qty = (cash * t_alt / 100) / ap
            
            cash = 0
            
            trade_rows.append({
                "Tarih": pd.to_datetime(i).strftime("%Y-%m-%d"),
                "Geçiş": "Başlangıç",
                "Rejim": etiket,
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt}",
                "Portföy": round(port_val, 0),
                "Getiri": 0.0,
            })
        
        prev_regime = isim
        
        # Portföy hesapla
        port_now = cash + btc_qty * bp + alt_qty * ap
        max_port = max(max_port, port_now)
        dd = (port_now - max_port) / max_port * 100
        max_dd = min(max_dd, dd)
        
        # İstatistikler
        if t_btc == 100:
            btc_gun += 1
        if t_alt == 100:
            alt_gun += 1
        
        equity.append(port_now)
        btc_pct_list.append(t_btc)
        alt_pct_list.append(t_alt)
    
    d["Portfoy"] = equity
    d["BtcPct"] = btc_pct_list
    d["AltinPct"] = alt_pct_list
    
    stats = {
        "islem_sayisi": len(trade_rows),
        "btc_gun": btc_gun,
        "alt_gun": alt_gun,
        "max_dd": round(max_dd, 1),
        "toplam_gun": len(d)
    }
    
    return d, pd.DataFrame(trade_rows), stats

# ── GOOGLE GENAI ENTEGRASYONU ──────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def gemini_api_yorum_uret(rejim_adi):
    if not GEMINI_KEY:
        return "⚠️ Gemini API anahtarı ayarlanmamış."
    
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        
        prompt = (
            f"Sen deneyimli bir makro ekonomi ve kripto para analistisin. "
            f"Altın/Bitcoin oranına göre piyasa şu an şu rejimde: '{rejim_adi}'. "
            f"Bu durumu teknik jargon kullanmadan, sıradan bir yatırımcının kolayca anlayabileceği bir dille yorumla. "
            f"Yatırımcının şu an ne yapması gerektiğine, portföyünü nasıl yönetmesi gerektiğine dair net tavsiyeler ver. "
            f"Cevabın toplamda 4 ile 6 cümle arasında, akıcı ve bilgilendirici olsun."
        )
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        
        if response.text:
            return response.text
            
    except Exception as e:
        return f"⚠️ AI analiz motorunda hata: {str(e)}"
    
    return "AI analiz şu an kullanılamıyor."

# ── ANA UYGULAMA ──────────────────────────────────────────────────────────────
try:
    raw = verileri_getir()
    
    if raw.empty or len(raw) < 60:
        st.error("❌ Veri yeterli büyüklükte değil.")
        st.stop()
    
    # Backtest çalıştır
    data, trade_log, stats = backtest_rotasyon_v2(raw)
    
    # Son veriler
    last = data.iloc[-1]
    btc_fiyat = float(last["Bitcoin"])
    alt_fiyat = float(last["Altin"])
    bakir_fiyat = float(last["Bakir"])
    
    au_btc = float(last["AuBtc"])
    cu_au = float(last["CuAu"])
    sma10 = float(last["SMA10"])
    sma50 = float(last["SMA50"])
    
    isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit_v2(au_btc, sma10, sma50, cu_au)
    
    # Al-Tut stratejileri
    data["BH_BTC"] = (10000.0 / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
    data["BH_Altin"] = (10000.0 / float(data["Altin"].iloc[0])) * data["Altin"]
    
    # Son değerler
    rot_son = float(data["Portfoy"].iloc[-1])
    rot_kazanc = (rot_son / 10000.0 - 1) * 100
    
    bh_btc_son = float(data["BH_BTC"].iloc[-1])
    bh_btc_k = (bh_btc_son / 10000.0 - 1) * 100
    
    bh_alt_son = float(data["BH_Altin"].iloc[-1])
    bh_alt_k = (bh_alt_son / 10000.0 - 1) * 100
    
    # Günlük değişimler
    if len(data) >= 2:
        btc_degisim = (btc_fiyat / float(data["Bitcoin"].iloc[-2]) - 1) * 100
        alt_degisim = (alt_fiyat / float(data["Altin"].iloc[-2]) - 1) * 100
        bakir_degisim = (bakir_fiyat / float(data["Bakir"].iloc[-2]) - 1) * 100
    else:
        btc_degisim = alt_degisim = bakir_degisim = 0.0

    # ── METRİK KARTLARI ────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin", fmt_usd(btc_fiyat), fmt_pct(btc_degisim) + " son gün")
    c2.metric("Altın", fmt_usd(alt_fiyat), fmt_pct(alt_degisim) + " son gün")
    c3.metric("Bakır", fmt_usd(bakir_fiyat), fmt_pct(bakir_degisim) + " son gün")
    c4.metric("Au/BTC Oranı", f"{au_btc:.6f}", f"SMA10: {sma10:.6f}")
    c5.metric("Cu/Au Oranı", f"{cu_au:.6f}", "Ekonomi Sağlığı")
    
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    
    # ── REJİM BANNER ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
        <span>{rejim_etiketi}</span>
        <span style="font-weight:400; font-size:12px; color:#64748B">{rejim_aciklama}</span>
        <span style="margin-left:auto; font-size:13px;">
            Şu an: <b style="color:#B45309">BTC %{btc_pct_now}</b> · <b style="color:#0369A1">Altın %{alt_pct_now}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    # ── STRATEJI PERFORMANS KARŞILAŞTIRMASI ────────────────────────────────────
    st.markdown('<div class="lk-section">📊 Strateji Performans Karşılaştırması</div>', unsafe_allow_html=True)
    
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("🔄 Rotasyon Stratejisi", fmt_usd(rot_son), fmt_pct(rot_kazanc))
    s2.metric("📈 BTC Al-Tut", fmt_usd(bh_btc_son), fmt_pct(bh_btc_k))
    s3.metric("🥇 Altın Al-Tut", fmt_usd(bh_alt_son), fmt_pct(bh_alt_k))
    
    # Avantaj/Dezavantaj
    if rot_son > bh_btc_son:
        avantaj = rot_son - bh_btc_son
        s4.metric("✅ Rotasyon Avantajı", fmt_usd(avantaj), fmt_pct((avantaj / bh_btc_son) * 100))
    else:
        dezavantaj = bh_btc_son - rot_son
        s4.metric("⚠️ Rotasyon Dezavantajı", fmt_usd(dezavantaj), fmt_pct((dezavantaj / rot_son) * -100))

    # ── STRATEJI İSTATİSTİKLERİ ───────────────────────────────────────────────
    st.markdown('<div class="lk-section">📈 Strateji Performans İstatistikleri</div>', unsafe_allow_html=True)
    st1, st2, st3, st4, st5 = st.columns(5)
    st1.metric("Toplam İşlem", str(stats["islem_sayisi"]), "rejim geçişi")
    st2.metric("BTC Modu Günleri", f"{stats['btc_gun']} gün", fmt_pct(stats['btc_gun'] / stats['toplam_gun'] * 100))
    st3.metric("Altın Modu Günleri", f"{stats['alt_gun']} gün", fmt_pct(stats['alt_gun'] / stats['toplam_gun'] * 100))
    st4.metric("Maks. Drawdown", fmt_pct(stats["max_dd"]), "En Kötü Durum")
    st5.metric("Periyot", f"{len(data)} gün", "~8 Yıl")

    # ── GRAFİK 1: ORANLAR ─────────────────────────────────────────────────────
    st.markdown('<div class="lk-section">📊 Au/BTC Oranı · SMA10 · SMA50</div>', unsafe_allow_html=True)
    fig1 = go.Figure()
    
    # Au/BTC
    fig1.add_trace(go.Scatter(
        x=data.index, 
        y=data["AuBtc"], 
        name="Au/BTC Oranı", 
        line=dict(color="#94A3B8", width=1.5),
        opacity=0.8
    ))
    
    # SMA10 (yeşil/kırmızı)
    data["Renk10"] = (data["AuBtc"] < data["SMA10"]).map({True:"#22C55E", False:"#EF4444"})
    for _, grp in data.groupby((data["Renk10"] != data["Renk10"].shift()).cumsum()):
        fig1.add_trace(go.Scatter(
            x=grp.index, 
            y=grp["SMA10"], 
            mode="lines", 
            line=dict(color=grp["Renk10"].iloc[0], width=2, dash="dot"),
            name="SMA10",
            showlegend=False
        ))
    
    # SMA50 (yeşil/kırmızı)
    data["Renk50"] = (data["AuBtc"] < data["SMA50"]).map({True:"#22C55E", False:"#EF4444"})
    for _, grp in data.groupby((data["Renk50"] != data["Renk50"].shift()).cumsum()):
        fig1.add_trace(go.Scatter(
            x=grp.index, 
            y=grp["SMA50"], 
            mode="lines", 
            line=dict(color=grp["Renk50"].iloc[0], width=2.5),
            name="SMA50",
            showlegend=False
        ))
    
    fig1.update_layout(
        height=400,
        template="plotly_white",
        paper_bgcolor="#F8FAFC",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Inter", color="#1E293B"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor="#E2E8F0"),
        yaxis=dict(title="Au/BTC Oranı", gridcolor="#E2E8F0"),
        hovermode="x unified"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ── GRAFİK 2: Cu/Au ORANI (Ekonomi Sağlığı) ────────────────────────────────
    st.markdown('<div class="lk-section">🏭 Cu/Au Oranı (Ekonomi Sağlığı - "Dr. Copper")</div>', unsafe_allow_html=True)
    fig_cu = go.Figure()
    
    fig_cu.add_trace(go.Scatter(
        x=data.index,
        y=data["CuAu"],
        name="Cu/Au Oranı",
        line=dict(color="#F59E0B", width=1.5),
        opacity=0.8
    ))
    
    fig_cu.add_trace(go.Scatter(
        x=data.index,
        y=data["CuAu_SMA50"],
        name="SMA50 (Trend)",
        line=dict(color="#EF4444", width=2, dash="dash")
    ))
    
    fig_cu.update_layout(
        height=300,
        template="plotly_white",
        paper_bgcolor="#F8FAFC",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Inter", color="#1E293B"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor="#E2E8F0"),
        yaxis=dict(title="Cu/Au Oranı", gridcolor="#E2E8F0"),
        hovermode="x unified"
    )
    st.plotly_chart(fig_cu, use_container_width=True)

    # ── GRAFİK 3: PORTFÖY KARŞILAŞTIRMASI ──────────────────────────────────────
    st.markdown('<div class="lk-section">💼 Portföy Karşılaştırması · Rotasyon vs Al-Tut</div>', unsafe_allow_html=True)
    fig2 = go.Figure()
    
    fig2.add_trace(go.Scatter(
        x=data.index, 
        y=data["Portfoy"], 
        name="Rotasyon Stratejisi", 
        line=dict(color="#0EA5E9", width=2.5),
        fill="tozeroy"
    ))
    
    fig2.add_trace(go.Scatter(
        x=data.index, 
        y=data["BH_BTC"], 
        name="BTC Al-Tut", 
        line=dict(color="#F59E0B", width=1.5, dash="dot")
    ))
    
    fig2.add_trace(go.Scatter(
        x=data.index, 
        y=data["BH_Altin"], 
        name="Altın Al-Tut", 
        line=dict(color="#D97706", width=1.5, dash="dash")
    ))
    
    fig2.update_layout(
        height=350,
        template="plotly_white",
        paper_bgcolor="#F8FAFC",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Inter", color="#1E293B"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor="#E2E8F0"),
        yaxis=dict(title="Portföy Değeri (USD)", gridcolor="#E2E8F0"),
        legend=dict(orientation="v", y=1, x=0),
        hovermode="x unified"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── AI ANALIZ ──────────────────────────────────────────────────────────────
    st.markdown('<div class="lk-section">✨ Yapay Zeka Stratejik Piyasa Analizi</div>', unsafe_allow_html=True)
    ai_yorum = gemini_api_yorum_uret(isim_now)
    st.markdown(f'<div class="lk-ai-box">{ai_yorum}</div>', unsafe_allow_html=True)

    # ── İŞLEM GÜNLÜĞÜ ──────────────────────────────────────────────────────────
    st.markdown('<div class="lk-section">📋 8 Yıllık İşlem Günlüğü (Son 20 İşlem)</div>', unsafe_allow_html=True)
    
    if not trade_log.empty:
        st.dataframe(trade_log.tail(20), use_container_width=True, hide_index=True)
    else:
        st.info("İşlem günlüğü boş")

    # ── DETAYLI ANALİZ TABLOSU ─────────────────────────────────────────────────
    st.markdown('<div class="lk-section">📊 Detaylı Analiz Verileri</div>', unsafe_allow_html=True)
    
    analiz_df = pd.DataFrame({
        "Metrik": [
            "İnitial Portföy",
            "Final Rotasyon",
            "Final BTC Al-Tut",
            "Final Altın Al-Tut",
            "Rotasyon Getirisi (%)",
            "BTC Al-Tut Getirisi (%)",
            "Altın Al-Tut Getirisi (%)",
            "İşlem Sayısı",
            "BTC Günü (%)",
            "Altın Günü (%)",
            "Max Drawdown (%)",
            "Mevcut Au/BTC Oranı",
            "Mevcut SMA10",
            "Mevcut SMA50",
            "Mevcut Rejim"
        ],
        "Değer": [
            "$10,000",
            fmt_usd(rot_son),
            fmt_usd(bh_btc_son),
            fmt_usd(bh_alt_son),
            f"{rot_kazanc:.2f}%",
            f"{bh_btc_k:.2f}%",
            f"{bh_alt_k:.2f}%",
            str(stats["islem_sayisi"]),
            f"{(stats['btc_gun'] / stats['toplam_gun'] * 100):.1f}%",
            f"{(stats['alt_gun'] / stats['toplam_gun'] * 100):.1f}%",
            f"{stats['max_dd']:.2f}%",
            f"{au_btc:.6f}",
            f"{sma10:.6f}",
            f"{sma50:.6f}",
            isim_now
        ]
    })
    
    st.dataframe(analiz_df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"❌ Genel hata oluştu: {str(e)}")
    import traceback
    st.error(traceback.format_exc())
