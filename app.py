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
.error-box { background: #FEE2E2; border: 1px solid #FECACA; border-radius: 8px; padding: 12px; margin: 10px 0; color: #991B1B; font-size: 13px; }
.success-box { background: #DCFCE7; border: 1px solid #BBF7D0; border-radius: 8px; padding: 12px; margin: 10px 0; color: #15803D; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / BTCUSD / CUUSD · Likidite Kompoziti · 8 Yıllık Analiz (V2.1 - DEBUG)</div>
    <p class="lk-title">Likidite Paneli - Hata Ayıklama Modu</p>
    <p class="lk-subtitle">Rejim Tespiti Detaylı Analizi</p>
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
    - cu_au: Bakır/Altın oranı (opsiyonel)
    """
    
    if pd.isna(au_btc) or pd.isna(sma10) or pd.isna(sma50):
        return ("Veri Yok", 50, 50, "unknown", "⚪ BİLİNMİYOR", "Yeterli veri yok")
    
    # Bakır/Altın sinyali (varsa ekle)
    cu_au_signal = 0.5  # Nötr
    if cu_au is not None and not pd.isna(cu_au):
        cu_au_sma50 = 0.0018  # Yaklaşık uzun dönem ortalama
        if cu_au > cu_au_sma50:
            cu_au_signal = 0.7  # Ekonomi güçlü
        else:
            cu_au_signal = 0.3  # Ekonomi zayıf
    
    # Ana sinyal: Au/BTC oranı
    if au_btc < sma10 and au_btc < sma50:
        return (
            "Güçlü Boğa (BTC)",
            int(80 + cu_au_signal * 20),
            int(20 - cu_au_signal * 20),
            "strong-on",
            "🟢 GÜÇLÜ BOĞA (BTC)",
            "BTC lehine güçlü sinyal · Risk-on ortamı"
        )
    elif au_btc < sma50:
        return (
            "Boğa + Düzeltme",
            int(60 + cu_au_signal * 10),
            int(40 - cu_au_signal * 10),
            "weak-on",
            "🟡 BOĞA + Kısa Toparlanma",
            "Büyük trend yukarı · Kısa vadede hafif konsolidasyon"
        )
    elif au_btc < sma10:
        return (
            "Ayı + Toparlanma",
            int(30 - cu_au_signal * 10),
            int(70 + cu_au_signal * 10),
            "weak-off",
            "🟠 AYI + Kısa Toparlanma",
            "Büyük trend aşağı · Kısa vadede geçici rahatlama"
        )
    else:
        return (
            "Güçlü Ayı (Altın)",
            int(20 - cu_au_signal * 20),
            int(80 + cu_au_signal * 20),
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
                st.error("Veri alınamadı.")
                return pd.DataFrame()
    
    return pd.DataFrame()

# ── BACKTEST V2 (DÜZELTILMIŞ) ─────────────────────────────────────────────────
def backtest_rotasyon_v2(df):
    """DÜZELTILMIŞ BACKTEST"""
    d = df.copy()
    
    d["AuBtc"] = d["Altin"] / d["Bitcoin"]
    d["CuAu"] = d["Bakir"] / d["Altin"]
    
    d["SMA10"] = d["AuBtc"].rolling(10).mean()
    d["SMA50"] = d["AuBtc"].rolling(50).mean()
    
    d["CuAu_SMA10"] = d["CuAu"].rolling(10).mean()
    d["CuAu_SMA50"] = d["CuAu"].rolling(50).mean()
    
    d = d.dropna().copy()
    
    if len(d) < 60:
        return d, pd.DataFrame(), {}
    
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
    
    transaction_cost = 0.001
    
    for idx, (i, row) in enumerate(d.iterrows()):
        au_btc = float(row["AuBtc"])
        cu_au = float(row["CuAu"])
        sma10 = float(row["SMA10"])
        sma50 = float(row["SMA50"])
        bp = float(row["Bitcoin"])
        ap = float(row["Altin"])
        
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit_v2(au_btc, sma10, sma50, cu_au)
        
        port_val = cash + btc_qty * bp + alt_qty * ap
        
        changed = (prev_regime is None) or (isim != prev_regime)
        
        if changed and prev_regime is not None:
            cash = cash + btc_qty * bp + alt_qty * ap
            cash *= (1 - transaction_cost)
            
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
        
        port_now = cash + btc_qty * bp + alt_qty * ap
        max_port = max(max_port, port_now)
        dd = (port_now - max_port) / max_port * 100
        max_dd = min(max_dd, dd)
        
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

# ── ANA UYGULAMA ──────────────────────────────────────────────────────────────
try:
    raw = verileri_getir()
    
    if raw.empty or len(raw) < 60:
        st.error("❌ Veri yeterli büyüklükte değil.")
        st.stop()
    
    data, trade_log, stats = backtest_rotasyon_v2(raw)
    
    last = data.iloc[-1]
    btc_fiyat = float(last["Bitcoin"])
    alt_fiyat = float(last["Altin"])
    bakir_fiyat = float(last["Bakir"])
    
    au_btc = float(last["AuBtc"])
    cu_au = float(last["CuAu"])
    sma10 = float(last["SMA10"])
    sma50 = float(last["SMA50"])
    
    isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit_v2(au_btc, sma10, sma50, cu_au)
    
    # ── HATA AYIKLAMAGRINDEKİ ANALIZLERI GÖR ──────────────────────────────────
    st.markdown('<div class="lk-section">🔍 HATA AYIKLAMA: Rejim Tespiti Analizi</div>', unsafe_allow_html=True)
    
    # Mevcut değerleri göster
    debug_col1, debug_col2, debug_col3, debug_col4 = st.columns(4)
    debug_col1.metric("Au/BTC Değeri", f"{au_btc:.8f}")
    debug_col2.metric("SMA10 Değeri", f"{sma10:.8f}")
    debug_col3.metric("SMA50 Değeri", f"{sma50:.8f}")
    debug_col4.metric("Cu/Au Değeri", f"{cu_au:.8f}")
    
    # Mevcut Rejim
    st.markdown(f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
        <span>{rejim_etiketi}</span>
        <span style="font-weight:400; font-size:12px; color:#64748B">{rejim_aciklama}</span>
    </div>""", unsafe_allow_html=True)
    
    # Karşılaştırmaları göster
    st.markdown("**Karşılaştırma Sonuçları:**")
    comp_col1, comp_col2, comp_col3 = st.columns(3)
    
    with comp_col1:
        if au_btc < sma10:
            st.markdown('<div class="success-box">✅ Au/BTC < SMA10 (DOĞRU)</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="error-box">❌ Au/BTC ≥ SMA10 (HATA)</div>', unsafe_allow_html=True)
    
    with comp_col2:
        if au_btc < sma50:
            st.markdown('<div class="success-box">✅ Au/BTC < SMA50 (DOĞRU)</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="error-box">❌ Au/BTC ≥ SMA50 (HATA)</div>', unsafe_allow_html=True)
    
    with comp_col3:
        diff_10 = au_btc - sma10
        diff_50 = au_btc - sma50
        st.write(f"**Fark SMA10:** {diff_10:+.8f}")
        st.write(f"**Fark SMA50:** {diff_50:+.8f}")
    
    # Rejim Dağılımını Analiz Et
    st.markdown('<div class="lk-section">📊 Rejim Dağılım Analizi (Son 2874 Gün)</div>', unsafe_allow_html=True)
    
    regime_counts = pd.Series(data["Rejim"]).value_counts()
    btc_pct_counts = data["BtcPct"].value_counts().sort_index(ascending=False)
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        st.write("**Rejim İsimlerine Göre Dağılım:**")
        for regime, count in regime_counts.items():
            pct = count / len(data) * 100
            st.write(f"- {regime}: {count} gün ({pct:.1f}%)")
    
    with col_dist2:
        st.write("**BTC % Dağılımına Göre Dağılım:**")
        for btc_pct, count in btc_pct_counts.items():
            alt_pct = 100 - btc_pct
            pct = count / len(data) * 100
            st.write(f"- BTC %{btc_pct} / Altın %{alt_pct}: {count} gün ({pct:.1f}%)")
    
    # İlk 50 satırın detayını göster
    st.markdown('<div class="lk-section">📋 İlk 50 Gün Detay (Au/BTC vs SMA10 vs SMA50)</div>', unsafe_allow_html=True)
    
    debug_detail = data[["AuBtc", "SMA10", "SMA50", "BtcPct", "Rejim"]].head(50).copy()
    debug_detail.columns = ["Au/BTC", "SMA10", "SMA50", "BTC %", "Rejim"]
    debug_detail["Au/BTC < SMA10?"] = (data["AuBtc"] < data["SMA10"]).head(50).astype(str)
    debug_detail["Au/BTC < SMA50?"] = (data["AuBtc"] < data["SMA50"]).head(50).astype(str)
    
    st.dataframe(debug_detail, use_container_width=True, hide_index=False)
    
    # Son 50 satırın detayını göster
    st.markdown('<div class="lk-section">📋 Son 50 Gün Detay</div>', unsafe_allow_html=True)
    
    debug_tail = data[["AuBtc", "SMA10", "SMA50", "BtcPct", "Rejim"]].tail(50).copy()
    debug_tail.columns = ["Au/BTC", "SMA10", "SMA50", "BTC %", "Rejim"]
    debug_tail["Au/BTC < SMA10?"] = (data["AuBtc"] < data["SMA10"]).tail(50).astype(str)
    debug_tail["Au/BTC < SMA50?"] = (data["AuBtc"] < data["SMA50"]).tail(50).astype(str)
    
    st.dataframe(debug_tail, use_container_width=True, hide_index=False)
    
    # Grafik: Au/BTC vs SMA10 vs SMA50
    st.markdown('<div class="lk-section">📊 Au/BTC vs SMA Oranları Grafiği</div>', unsafe_allow_html=True)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=data.index, 
        y=data["AuBtc"], 
        name="Au/BTC", 
        line=dict(color="#94A3B8", width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=data.index, 
        y=data["SMA10"], 
        name="SMA10", 
        line=dict(color="#0EA5E9", width=2, dash="dot")
    ))
    
    fig.add_trace(go.Scatter(
        x=data.index, 
        y=data["SMA50"], 
        name="SMA50", 
        line=dict(color="#EF4444", width=2, dash="dash")
    ))
    
    fig.update_layout(
        height=500,
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
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Sonuç Analizi
    st.markdown('<div class="lk-section">🎯 Sorun Özeti</div>', unsafe_allow_html=True)
    
    if stats["btc_gun"] == 0 and stats["alt_gun"] == 0:
        st.markdown("""
        <div class="error-box">
        ❌ <b>KRİTİK SORUN TESPIT EDİLDİ:</b><br>
        - 0 gün %100 BTC modu<br>
        - 0 gün %100 Altın modu<br>
        - Her gün sadece 50-70% arasında BTC pozisyonu<br>
        <br>
        <b>Kök Neden:</b> Rejim tespit fonksiyonu hiçbir şarta tam olarak uymuyor!<br>
        Muhtemelen Au/BTC değerleri her zaman arası değerlerde kalıyor.<br>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="success-box">
        ✅ Rejim Tespiti Çalışıyor
        </div>
        """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"❌ Genel hata oluştu: {str(e)}")
    import traceback
    st.error(traceback.format_exc())
