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
st.set_page_config(page_title="Likidite Kompozit Paneli v3.1", layout="wide", page_icon="◆")

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
.success-box { background: #DCFCE7; border: 1px solid #BBF7D0; border-radius: 8px; padding: 12px; margin: 10px 0; color: #15803D; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / BTCUSD · Likidite Analizi · 8 Yıllık Backtest (V3.1 - GÜVENLI)</div>
    <p class="lk-title">Likidite Paneli - Rejim Tespiti Düzeltildi</p>
    <p class="lk-subtitle">SMA10 vs SMA50 Trend + Au/BTC Momentum Stratejisi</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="success-box">
✅ <b>V3.1 Güvenlik Güncellemesi:</b><br>
• Boş veri kontrolleri eklendi<br>
• data.iloc[-1] öncesi validasyon<br>
• Hata toleransı geliştirildi<br>
</div>
""", unsafe_allow_html=True)

# ── SECRETS / ENV CONFIG ──────────────────────────────────────────────────────
GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()

# ── REJİM FONKSİYONU V3 (DÜZELTILMIŞ MANTIK) ──────────────────────────────────
def rejim_tespit_v3(au_btc, sma10, sma50, cu_au=None):
    """
    V3 DÜZELTILMIŞ MANTIK:
    
    Eksen 1: SMA Trendi
    - sma10 < sma50: Trend YUKARIDA (Boğa) 
    - sma10 > sma50: Trend AŞAĞIDA (Ayı)
    
    Eksen 2: Au/BTC Pozisyonu
    - au_btc < sma10: Kısa dönem güçlü (BTC tarafı)
    - au_btc > sma10: Kısa dönem zayıf (Altın tarafı)
    
    Kombinasyonlar:
    🟢 Güçlü Boğa: au_btc < sma10 AND sma10 < sma50 (Çift BTC)
    🟡 Boğa:      au_btc > sma10 AND sma10 < sma50 (Trend yukarı, geçici düzeltme)
    🟠 Ayı:       au_btc < sma10 AND sma10 > sma50 (Trend aşağı, geçici rally)
    🔴 Güçlü Ayı:  au_btc > sma10 AND sma10 > sma50 (Çift Altın)
    """
    
    if pd.isna(au_btc) or pd.isna(sma10) or pd.isna(sma50):
        return ("Veri Yok", 50, 50, "unknown", "⚪ BİLİNMİYOR", "Yeterli veri yok")
    
    # Cu/Au ekonomi sinyali
    cu_au_signal = 0.5
    if cu_au is not None and not pd.isna(cu_au):
        cu_au_sma = 0.0018
        if cu_au > cu_au_sma:
            cu_au_signal = 0.7  # Ekonomi güçlü
        else:
            cu_au_signal = 0.3  # Ekonomi zayıf
    
    # Ana Mantık
    au_is_bullish = au_btc < sma10      # Kısa dönem
    sma_is_bullish = sma10 < sma50      # Uzun dönem
    
    if au_is_bullish and sma_is_bullish:
        # 🟢 Çift Boğa
        return (
            "Güçlü Boğa",
            100,
            0,
            "strong-on",
            "🟢 GÜÇLÜ BOĞA (BTC)",
            "Kısa ve uzun dönem BTC lehine · En güçlü alım sinyali"
        )
    elif not au_is_bullish and sma_is_bullish:
        # 🟡 Trend Boğa ama Kısa Düzeltme
        return (
            "Boğa + Düzeltme",
            70,
            30,
            "weak-on",
            "🟡 BOĞA + Kısa Düzeltme",
            "Uzun dönem trend yukarı · Kısa vadede konsolidasyon"
        )
    elif au_is_bullish and not sma_is_bullish:
        # 🟠 Trend Ayı ama Kısa Rally
        return (
            "Ayı + Toparlanma",
            30,
            70,
            "weak-off",
            "🟠 AYI + Kısa Toparlanma",
            "Uzun dönem trend aşağı · Kısa vadede geçici rahatlama"
        )
    else:
        # 🔴 Çift Ayı
        return (
            "Güçlü Ayı",
            0,
            100,
            "strong-off",
            "🔴 GÜÇLÜ AYI (Altın)",
            "Kısa ve uzun dönem Altın lehine · En güçlü korunma modu"
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
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df = df["Close"].copy()
            elif "Close" in df.columns:
                df = df["Close"]
            
            df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
            
            cols = [c for c in ["Altin", "Bakir", "Bitcoin"] if c in df.columns]
            df = df[cols].ffill().bfill()
            
            if len(df) < 60:
                continue
            
            return df
            
        except Exception as e:
            if attempt < 2:
                continue
            else:
                st.error("❌ Veri alınamadı.")
                return pd.DataFrame()
    
    return pd.DataFrame()

# ── BACKTEST V3.1 (GÜVENLI VERSİYON) ───────────────────────────────────────────
def backtest_rotasyon_v3(df):
    """DÜZELTILMIŞ BACKTEST V3 - GÜVENLI VERSİYON"""
    d = df.copy()
    
    # Rasyoları hesapla
    d["AuBtc"] = d["Altin"] / d["Bitcoin"]
    d["CuAu"] = d["Bakir"] / d["Altin"]
    
    # SMA'ları hesapla
    d["SMA10"] = d["AuBtc"].rolling(10).mean()
    d["SMA50"] = d["AuBtc"].rolling(50).mean()
    d["CuAu_SMA50"] = d["CuAu"].rolling(50).mean()
    
    d = d.dropna().copy()
    
    # 🛡️ GÜVENLIK KONTROLÜ 1: Dropna sonrası kontrol
    if d.empty or len(d) < 60:
        empty_stats = {
            "islem_sayisi": 0,
            "btc_gun": 0,
            "alt_gun": 0,
            "max_dd": 0.0,
            "toplam_gun": 0
        }
        return pd.DataFrame(), pd.DataFrame(), empty_stats
    
    # Portföy simülasyonu
    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows = []
    equity = []
    btc_pct_list = []
    alt_pct_list = []
    regime_names = []
    
    btc_gun = alt_gun = 0
    max_port = 10000.0
    max_dd = 0.0
    
    transaction_cost = 0.001  # %0.1
    
    for idx, (i, row) in enumerate(d.iterrows()):
        au_btc = float(row["AuBtc"])
        cu_au = float(row["CuAu"])
        sma10 = float(row["SMA10"])
        sma50 = float(row["SMA50"])
        bp = float(row["Bitcoin"])
        ap = float(row["Altin"])
        
        # Rejim tespit et (V3)
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit_v3(au_btc, sma10, sma50, cu_au)
        
        # Mevcut portföy değeri
        port_val = cash + btc_qty * bp + alt_qty * ap
        
        # Rejim değişikliği kontrol et
        changed = (prev_regime is None) or (isim != prev_regime)
        
        if changed and prev_regime is not None:
            # Rejim değişti - pozisyon geçişi yap
            cash = cash + btc_qty * bp + alt_qty * ap
            cash *= (1 - transaction_cost)
            
            # Yeni pozisyonu aç
            if t_btc == 0:
                btc_qty = 0
                alt_qty = cash / ap if ap > 0 else 0
            elif t_alt == 0:
                alt_qty = 0
                btc_qty = cash / bp if bp > 0 else 0
            else:
                btc_qty = (cash * t_btc / 100) / bp if bp > 0 else 0
                alt_qty = (cash * t_alt / 100) / ap if ap > 0 else 0
            
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
                alt_qty = cash / ap if ap > 0 else 0
            elif t_alt == 0:
                alt_qty = 0
                btc_qty = cash / bp if bp > 0 else 0
            else:
                btc_qty = (cash * t_btc / 100) / bp if bp > 0 else 0
                alt_qty = (cash * t_alt / 100) / ap if ap > 0 else 0
            
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
        dd = (port_now - max_port) / max_port * 100 if max_port > 0 else 0
        max_dd = min(max_dd, dd)
        
        # İstatistikler
        if t_btc == 100:
            btc_gun += 1
        if t_alt == 100:
            alt_gun += 1
        
        equity.append(port_now)
        btc_pct_list.append(t_btc)
        alt_pct_list.append(t_alt)
        regime_names.append(isim)
    
    d["Portfoy"] = equity
    d["BtcPct"] = btc_pct_list
    d["AltinPct"] = alt_pct_list
    d["Rejim"] = regime_names
    
    stats = {
        "islem_sayisi": len(trade_rows),
        "btc_gun": btc_gun,
        "alt_gun": alt_gun,
        "max_dd": round(max_dd, 1),
        "toplam_gun": len(d)
    }
    
    return d, pd.DataFrame(trade_rows), stats

# ── GOOGLE GENAI ────────────────────────────────────────────────────────────────
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
            f"Bu durumu teknik jargon kullanmadan, sıradan bir yatırımcının kolayca anlayabileceği bir dilde yorumla. "
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
        return f"⚠️ AI analiz motorunda hata"
    
    return "AI analiz şu an kullanılamıyor."

# ── ANA UYGULAMA ──────────────────────────────────────────────────────────────
try:
    raw = verileri_getir()
    
    if raw.empty or len(raw) < 60:
        st.error("❌ Veri yeterli büyüklükte değil (minimum 60 gün gerekli).")
        st.stop()
    
    # Backtest çalıştır
    data, trade_log, stats = backtest_rotasyon_v3(raw)
    
    # 🛡️ GÜVENLIK KONTROLÜ 2: data.iloc[-1] öncesi validasyon
    if data.empty or len(data) < 2:
        st.error("❌ Backtest veri işleme hatası: Yeterli satır yok.")
        st.stop()
    
    # Son veriler
    last = data.iloc[-1]
    btc_fiyat = float(last["Bitcoin"])
    alt_fiyat = float(last["Altin"])
    bakir_fiyat = float(last["Bakir"])
    
    au_btc = float(last["AuBtc"])
    cu_au = float(last["CuAu"])
    sma10 = float(last["SMA10"])
    sma50 = float(last["SMA50"])
    
    isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit_v3(au_btc, sma10, sma50, cu_au)
    
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
        s4.metric("⚠️ Dezavantaj", fmt_usd(dezavantaj), fmt_pct((dezavantaj / rot_son) * -100))

    # ── STRATEJI İSTATİSTİKLERİ ───────────────────────────────────────────────
    st.markdown('<div class="lk-section">📈 Strateji Performans İstatistikleri</div>', unsafe_allow_html=True)
    st1, st2, st3, st4, st5 = st.columns(5)
    st1.metric("Toplam İşlem", str(stats["islem_sayisi"]), "rejim geçişi")
    st2.metric("100% BTC Günleri", f"{stats['btc_gun']} gün", fmt_pct(stats['btc_gun'] / stats['toplam_gun'] * 100) if stats['toplam_gun'] > 0 else "0%")
    st3.metric("100% Altın Günleri", f"{stats['alt_gun']} gün", fmt_pct(stats['alt_gun'] / stats['toplam_gun'] * 100) if stats['toplam_gun'] > 0 else "0%")
    st4.metric("Maks. Drawdown", fmt_pct(stats["max_dd"]), "En Kötü Durum")
    st5.metric("Periyot", f"{len(data)} gün", "~8 Yıl")

    # ── GRAFİK 1: ORANLAR ─────────────────────────────────────────────────────
    st.markdown('<div class="lk-section">📊 Au/BTC Oranı · SMA10 · SMA50</div>', unsafe_allow_html=True)
    fig1 = go.Figure()
    
    fig1.add_trace(go.Scatter(
        x=data.index, 
        y=data["AuBtc"], 
        name="Au/BTC Oranı", 
        line=dict(color="#94A3B8", width=1.5),
        opacity=0.8
    ))
    
    fig1.add_trace(go.Scatter(
        x=data.index, 
        y=data["SMA10"], 
        name="SMA10 (Kısa Dönem)", 
        line=dict(color="#0EA5E9", width=2, dash="dot")
    ))
    
    fig1.add_trace(go.Scatter(
        x=data.index, 
        y=data["SMA50"], 
        name="SMA50 (Uzun Dönem)", 
        line=dict(color="#EF4444", width=2.5)
    ))
    
    fig1.update_layout(
        height=400,
        template="plotly_white",
        paper_bgcolor="#F8FAFC",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Inter", color="#1E293B"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor="#E2E8F0"),
        yaxis=dict(title="Oran Değeri", gridcolor="#E2E8F0"),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0)
    )
    
    st.plotly_chart(fig1, use_container_width=True)

    # ── GRAFİK 2: PORTFÖY KARŞILAŞTIRMASI ──────────────────────────────────────
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
        st.info("ℹ️ İşlem günlüğü boş - rejim geçişi henüz başlamadı")

    # ── REJİM DAĞILIMI ──────────────────────────────────────────────────────────
    st.markdown('<div class="lk-section">📊 Rejim Dağılım Analizi</div>', unsafe_allow_html=True)
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        st.write("**Rejim İsimlerine Göre Dağılım:**")
        regime_counts = pd.Series(data["Rejim"]).value_counts()
        for regime, count in regime_counts.items():
            pct = count / len(data) * 100 if len(data) > 0 else 0
            st.write(f"• {regime}: {count} gün ({pct:.1f}%)")
    
    with col_dist2:
        st.write("**BTC % Dağılımına Göre Dağılım:**")
        btc_pct_counts = data["BtcPct"].value_counts().sort_index(ascending=False)
        for btc_pct, count in btc_pct_counts.head(10).items():
            alt_pct = 100 - btc_pct
            pct = count / len(data) * 100 if len(data) > 0 else 0
            st.write(f"• BTC %{btc_pct} / Altın %{alt_pct}: {count} gün ({pct:.1f}%)")

    # ── DETAYLI ÖZET ───────────────────────────────────────────────────────────
    st.markdown('<div class="lk-section">📊 Detaylı Özet</div>', unsafe_allow_html=True)
    
    summary_data = {
        "Metrik": [
            "İnitial Portföy",
            "Final Rotasyon",
            "Final BTC Al-Tut",
            "Final Altın Al-Tut",
            "Rotasyon Getirisi (%)",
            "BTC Al-Tut Getirisi (%)",
            "Altın Al-Tut Getirisi (%)",
            "Toplam İşlem",
            "100% BTC Günü (%)",
            "100% Altın Günü (%)",
            "Max Drawdown (%)",
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
            f"{(stats['btc_gun'] / stats['toplam_gun'] * 100):.1f}%" if stats['toplam_gun'] > 0 else "0%",
            f"{(stats['alt_gun'] / stats['toplam_gun'] * 100):.1f}%" if stats['toplam_gun'] > 0 else "0%",
            f"{stats['max_dd']:.2f}%",
            isim_now
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"❌ Genel hata oluştu: {str(e)}")
    import traceback
    st.error(traceback.format_exc())
