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
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / XCUUSD / BTCUSD · Likidite Kompoziti · 8 Yıllık Analiz</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Altın · Bakır · Bitcoin rasyosu üzerinden küresel likidite yönünü ve fırsatları takip et</p>
</div>
""", unsafe_allow_html=True)

# ── SECRETS ───────────────────────────────────────────────────────────────────
GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()

# ── REJİM FONKSİYONU ──────────────────────────────────────────────────────────
def rejim_tespit(r, s10, s50):
    if r < s10 and r < s50:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢 GÜÇLÜ BOĞA", "Her iki sinyal BTC lehine · En güçlü alım bölgesi")
    elif r < s50:
        return ("Boğa + Düzeltme", 50, 50, "weak-on", "🟡 BOĞA + Kısa Düzeltme", "Büyük trend yukarı · Kısa vadede hafif baskı")
    elif r < s10:
        return ("Ayı + Toparlanma", 0, 100, "weak-off", "🟠 AYI + Kısa Toparlanma", "Büyük trend aşağı · Kısa vadede geçici rahatlama")
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴 GÜÇLÜ AYI", "Her iki sinyal BTC aleyhine · Altın koruma modu")

def fmt_pct(x): return f"%{x:+.1f}"
def fmt_usd(x): return f"${x:,.0f}"

def load_state():
    try:
        return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8")) if ALERT_STATE_FILE.exists() else {}
    except Exception: return {}

def save_state(s):
    try: ALERT_STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception: pass

def telegram_gonder(mesaj):
    if not TOKEN or not CHAT_ID: return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
        return r.ok
    except Exception: return False

@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
    df = yf.download(list(symbols.keys()), period="8y", interval="1d", auto_adjust=False, multi_level_index=False, progress=False)
    if df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df = df["Close"].copy() if "Close" in df.columns.get_level_values(0) else df.set_axis(df.columns.get_level_values(0), axis=1)
    elif "Close" in df.columns:
        df = df["Close"]
    df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
    cols = [c for c in ["Altin", "Bakir", "Bitcoin"] if c in df.columns]
    return df[cols].ffill().bfill()

# ── GÜNDE BİR KERE ARKA PLAN KONTROLÜ (SAAT 10:00) ───────────────────────────
def günlük_rejim_kontrol_ve_bildir():
    try:
        symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
        df = yf.download(list(symbols.keys()), period="60d", interval="1d", auto_adjust=False, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df = df["Close"]
        df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
        df = df[["Altin","Bakir","Bitcoin"]].ffill().bfill().dropna()
        if len(df) < 52: return
        
        df["Rasyo"] = df["Altin"] / (df["Bakir"] * df["Bitcoin"])
        df["SMA10"] = df["Rasyo"].rolling(10).mean()
        df["SMA50"] = df["Rasyo"].rolling(50).mean()
        last = df.dropna().iloc[-1]
        
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(float(last["Rasyo"]), float(last["SMA10"]), float(last["SMA50"]))
        state = load_state()
        bugun_str = datetime.now().strftime("%Y-%m-%d")
        
        if state.get("son_rapor_tarihi") != bugun_str:
            mesaj = (
                f"📊 *GÜNLÜK LİKİDİTE REJİM RAPORU*\n\n"
                f"Durum: *{etiket}*\n"
                f"🪙 BTC Fiyat: {fmt_usd(float(last['Bitcoin']))}\n"
                f"🥇 Altın Fiyat: {fmt_usd(float(last['Altin']))}\n"
                f"💼 İdeal Dağılım: BTC %{t_btc} · Altın %{t_alt}\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            if telegram_gonder(mesaj):
                state["son_rapor_tarihi"] = bugun_str
        
        state.update({
            "rejim": etiket,
            "son_kontrol": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "btc_fiyat": round(float(last["Bitcoin"]), 0),
            "alt_fiyat": round(float(last["Altin"]), 0),
        })
        save_state(state)
    except Exception:
        pass

if SCHEDULER_OK and "scheduler_started" not in st.session_state:
    _sch = BackgroundScheduler(timezone="Europe/Istanbul")
    _sch.add_job(günlük_rejim_kontrol_ve_bildir, "cron", hour=10, minute=0, id="gunluk_kontrol", replace_existing=True)
    _sch.start()
    st.session_state["scheduler_started"] = True

# ── BACKTEST VE HESAPLAMALAR ──────────────────────────────────────────────────
def backtest_rotasyon(df):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d = d.dropna().copy()
    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows, equity, btc_pct_list, alt_pct_list = [], [], [], []
    btc_gun = alt_gun = 0
    max_port = 10000.0
    max_dd = 0.0
    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        bp, ap = float(row["Bitcoin"]), float(row["Altin"])
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(r, s10, s50)
        port_val = cash + btc_qty * bp + alt_qty * ap
        changed = (prev_regime is None) or (isim != prev_regime)
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
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'Başlangıç'} → {isim}",
                "Rejim": etiket,
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt}",
                "Portföy": round(port_after, 0),
                "Getiri": round((port_after / 10000.0 - 1) * 100, 1),
            })
            prev_regime = isim
        port_now = cash + btc_qty * bp + alt_qty * ap
        max_port = max(max_port, port_now)
        dd = (port_now - max_port) / max_port * 100
        max_dd = min(max_dd, dd)
        if t_btc == 100: btc_gun += 1
        if t_alt == 100: alt_gun += 1
        equity.append(port_now)
        btc_pct_list.append(t_btc)
        alt_pct_list.append(t_alt)
    d["Portfoy"] = equity
    d["BtcPct"] = btc_pct_list
    d["AltinPct"] = alt_pct_list
    stats = {"islem_sayisi": len(trade_rows), "btc_gun": btc_gun, "alt_gun": alt_gun, "max_dd": round(max_dd, 1), "toplam_gun": len(d)}
    return d, pd.DataFrame(trade_rows), stats

@st.cache_data(ttl=3600)
def gemini_api_yorum_uret(rejim_adi):
    if not GEMINI_KEY:
        return "Gemini API anahtarı ayarlanmamış. Analiz üretilemiyor."
    
    prompt = (
        f"Sen deneyimli bir makro ekonomi ve kripto para analistisin. "
        f"Küresel likidite rasyolarına göre piyasa şu an şu rejimde: '{rejim_adi}'. "
        f"Bu durumu teknik jargon kullanmadan, sıradan bir yatırımcının kolayca anlayabileceği bir dille yorumla. "
        f"Yatırımcının şu an ne yapması gerektiğine, portföyünü nasıl yönetmesi gerektiğine dair net tavsiyeler ver. "
        f"Cevabın toplamda 4 ile 6 cümle arasında, akıcı ve bilgilendirici olsun."
    )
    
    for model in ["gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-2.0-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if r.status_code == 429: continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception: continue
    return "Yapay zeka analiz motoruna şu an erişilemiyor. Lütfen daha sonra tekrar deneyin."

# ── ANA UYGULAMA GÖRÜNÜMÜ ─────────────────────────────────────────────────────
try:
    raw = verileri_getir()
    if raw.empty or len(raw) < 60:
        st.error("Veri yeterli büyüklükte değil.")
        st.stop()
        
    data, trade_log, stats = backtest_rotasyon(raw)
    last = data.iloc[-1]
    btc_fiyat = float(last["Bitcoin"])
    alt_fiyat = float(last["Altin"])
    son_rasyo = float(last["Rasyo"])
    sma10, sma50 = float(last["SMA10"]), float(last["SMA50"])
    kisa_bull, makro_bull = son_rasyo < sma10, son_rasyo < sma50
    
    isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit(son_rasyo, sma10, sma50)
    
    data["BH_BTC"] = (10000.0 / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
    data["BH_Altin"] = (10000.0 / float(data["Altin"].iloc[0])) * data["Altin"]
    rot_son = float(data["Portfoy"].iloc[-1])
    rot_kazanc = (rot_son / 10000.0 - 1) * 100
    bh_btc_son = float(data["BH_BTC"].iloc[-1])
    bh_btc_k = (bh_btc_son / 10000.0 - 1) * 100
    bh_alt_son = float(data["BH_Altin"].iloc[-1])
    bh_alt_k = (bh_alt_son / 10000.0 - 1) * 100
    btc_degisim = (btc_fiyat / float(data["Bitcoin"].iloc[-2]) - 1) * 100
    alt_degisim = (alt_fiyat / float(data["Altin"].iloc[-2]) - 1) * 100

    # Metrik Kartları
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin", fmt_usd(btc_fiyat), fmt_pct(btc_degisim) + " son gün")
    c2.metric("Altın", fmt_usd(alt_fiyat), fmt_pct(alt_degisim) + " son gün")
    c3.metric("8Y Rotasyon", fmt_usd(rot_son), fmt_pct(rot_kazanc))
    c4.metric("BTC Al-Tut", fmt_usd(bh_btc_son), fmt_pct(bh_btc_k))
    c5.metric("Altın Al-Tut", fmt_usd(bh_alt_son), fmt_pct(bh_alt_k))
    
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    
    # Rejim Banner
    st.markdown(f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
        <span>{rejim_etiketi}</span>
        <span style="font-weight:400; font-size:12px; color:#64748B">{rejim_aciklama}</span>
        <span style="margin-left:auto; font-size:13px;">
            Şu an: <b style="color:#B45309">BTC %{btc_pct_now}</b> · <b style="color:#0369A1">Altın %{alt_pct_now}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    # Performans İstatistikleri
    st.markdown('<div class="lk-section">Strateji Performans İstatistikleri</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Toplam İşlem", str(stats["islem_sayisi"]), "rejim geçişi")
    s2.metric("BTC'de Geçen Süre", f"{stats['btc_gun']} gün", fmt_pct(stats['btc_gun'] / stats['toplam_gun'] * 100))
    s3.metric("Altın'da Geçen Süre", f"{stats['alt_gun']} gün", fmt_pct(stats['alt_gun'] / stats['toplam_gun'] * 100))
    s4.metric("Maks. Drawdown", fmt_pct(stats["max_dd"]))
    s5.metric("Rotasyon Avantajı", fmt_usd(rot_son - bh_btc_son))

    # Grafik 1: Aydınlık Temalı Likidite Grafiği
    st.markdown('<div class="lk-section">Likidite Rasyosu · SMA10 · SMA50 · BTC Fiyatı</div>', unsafe_allow_html=True)
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Rasyo", line=dict(color="#94A3B8", width=1.0), opacity=0.7))
    
    data["Renk10"] = (data["Rasyo"] < data["SMA10"]).map({True:"#22C55E", False:"#EF4444"})
    for _, grp in data.groupby((data["Renk10"] != data["Renk10"].shift()).cumsum()):
        fig1.add_trace(go.Scatter(x=grp.index, y=grp["SMA10"], mode="lines", line=dict(color=grp["Renk10"].iloc[0], width=1.5, dash="dot"), showlegend=False))
        
    data["Renk50"] = (data["Rasyo"] < data["SMA50"]).map({True:"#22C55E", False:"#EF4444"})
    for _, grp in data.groupby((data["Renk50"] != data["Renk50"].shift()).cumsum()):
        fig1.add_trace(go.Scatter(x=grp.index, y=grp["SMA50"], mode="lines", line=dict(color=grp["Renk50"].iloc[0], width=2.5), showlegend=False))
        
    fig1.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC Fiyatı", line=dict(color="#F59E0B", width=1.2, dash="dot"), yaxis="y2"))
    
    fig1.update_layout(
        height=450, template="plotly_white", paper_bgcolor="#F8FAFC", plot_bgcolor="#FFFFFF",
        font=dict(family="Inter", color="#1E293B"), margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(title="Rasyo", gridcolor="#E2E8F0"),
        yaxis2=dict(title="BTC (USD)", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)")
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Yapay Zeka Yorum Alanı
    st.markdown('<div class="lk-section">✨ Yapay Zeka Stratejik Piyasa Analizi</div>', unsafe_allow_html=True)
    ai_yorum = gemini_api_yorum_uret(isim_now)
    st.markdown(f'<div class="lk-ai-box">{ai_yorum}</div>', unsafe_allow_html=True)

    # Grafik 2: Portföy Karşılaştırma
    st.markdown('<div class="lk-section">Portföy Karşılaştırma · Rotasyon vs BTC Al-Tut vs Altın Al-Tut</div>', unsafe_allow_html=True)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="BTC+Altın Rotasyon", line=dict(color="#0EA5E9", width=2.5)))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="BTC Al-Tut", line=dict(color="#F59E0B", width=1.5, dash="dot")))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Altın Al-Tut", line=dict(color="#D97706", width=1.5, dash="dash")))
    fig2.update_layout(
        height=350, template="plotly_white", paper_bgcolor="#F8FAFC", plot_bgcolor="#FFFFFF",
        font=dict(family="Inter", color="#1E293B"), margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(title="Portföy Değeri (USD)", gridcolor="#E2E8F0"),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)")
    )
    st.plotly_chart(fig2, use_container_width=True)

    # İşlem Günlüğü
    st.markdown('<div class="lk-section">8 Yıllık İşlem Günlüğü</div>', unsafe_allow_html=True)
    st.dataframe(trade_log, use_container_width=True, hide_index=True)

    # Alarm Durumu Metrikleri
    st.markdown('<div class="lk-section">Otomatik Alarm Sistemi Durumu</div>', unsafe_allow_html=True)
    state = load_state()
    a1, a2, a3 = st.columns(3)
    a1.metric("Kontrol Sıklığı", "Günde 1 Kez (10:00)", "✅ Aktif" if SCHEDULER_OK else "⚠️ Sorun Var")
    a2.metric("Son Güncelleme", state.get("son_kontrol", "Bekleniyor"), f"BTC {fmt_usd(state.get('btc_fiyat', 0))}" if "btc_fiyat" in state else "")
    a3.metric("Son Gönderilen Rapor", state.get("son_rapor_tarihi", "Henüz Yok"), "Telegram Bildirimi")

except Exception as e:
    st.error(f"Genel hata oluştu: {e}")
