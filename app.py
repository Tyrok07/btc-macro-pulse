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

# ── CSS ───────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# TEMA — "dark" veya "light" yazarak tüm renkleri değiştir
# ══════════════════════════════════════════════════════════════════════════════
TEMA = "light"   # ← SADECE BU SATIRI DEĞİŞTİR

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
.lk-regime-strong-off {{ background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.4); color: #EF4444; }}
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
    <div class="lk-eyebrow">XAUUSD / XCUUSD / BTCUSD · Likidite Kompoziti · 8 Yıllık Analiz</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Altın · Bakır · Bitcoin rasyosu üzerinden küresel likidite yönünü ve fırsatları takip et</p>
</div>
""", unsafe_allow_html=True)

# ── SECRETS ───────────────────────────────────────────────────────────────────
GEMINI_KEY      = str(st.secrets.get("GEMINI_API_KEY",  "")).strip()
TOKEN           = str(st.secrets.get("TELEGRAM_TOKEN",  "")).strip()
CHAT_ID         = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()
KONTROL_ARALIK  = 140  # dakika

# ══════════════════════════════════════════════════════════════════════════════
# TEK REJİM FONKSİYONU — hem backtest hem UI hem scheduler burayı kullanır.
# ══════════════════════════════════════════════════════════════════════════════
def rejim_tespit(r, s10, s50):
    if r < s10 and r < s50:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢🟢 GÜÇLÜ BOĞA", "Her iki sinyal BTC lehine · En güçlü alım bölgesi")
    elif r < s50:
        return ("Boğa + Düzeltme", 50, 50, "weak-on", "🟡🟢 BOĞA + Kısa Düzeltme", "Büyük trend yukarı · Kısa vadede hafif baskı")
    elif r < s10:
        return ("Ayı + Toparlanma", 0, 100, "weak-off", "🟠🔴 AYI + Kısa Toparlanma", "Büyük trend aşağı · Kısa vadede geçici rahatlama")
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴🔴 GÜÇLÜ AYI", "Her iki sinyal BTC aleyhine · Altın koruma modu")

# ── YARDIMCI FONKSİYONLAR ────────────────────────────────────────────────────
def fmt_pct(x): return f"%{x:+.1f}"
def fmt_usd(x): return f"${x:,.0f}"

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

# ── VERİ ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
    df = yf.download(list(symbols.keys()), period="8y", interval="1d",
                     auto_adjust=False, multi_level_index=False, progress=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df = df["Close"].copy() if "Close" in df.columns.get_level_values(0) else df.set_axis(df.columns.get_level_values(0), axis=1)
    elif "Close" in df.columns:
        df = df["Close"]
    df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
    cols = [c for c in ["Altin", "Bakir", "Bitcoin"] if c in df.columns]
    return df[cols].ffill().bfill()

# ── GEMİNİ ───────────────────────────────────────────────────────────────────
def gemini_api(prompt):
    if not GEMINI_KEY:
        return None
    for model in ["gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-2.0-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if r.status_code == 429:
                continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    return None

@st.cache_data(ttl=1800)
def gemini_yorum_cache(btc_r, rejim, rot_k, bh_btc_k, bh_alt_k, kisa_bull, makro_bull):
    prompt = f"""
Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının
anlayabileceği sade Türkçe ile 4-6 cümlelik özet yorum yaz. Teknik jargon kullanma.
Sonunda tek cümleyle "Şu an ne yapmalı?" önerisi ver.

- Bitcoin: ${btc_r:,.0f}
- Rejim: {rejim}
- Kısa vade (SMA10): {"Boğa" if kisa_bull else "Ayı"}
- Uzun vade (SMA50): {"Boğa" if makro_bull else "Ayı"}
- 8Y Rotasyon kazancı: {fmt_pct(rot_k)}
- BTC al-tut kıyası: {fmt_pct(bh_btc_k)}
- Altın al-tut kıyası: {fmt_pct(bh_alt_k)}

Sadece yorum metni yaz, madde işareti veya başlık ekleme.
"""
    return gemini_api(prompt)

# ── BACKTEST ─────────────────────────────────────────────────────────────────
def backtest_rotasyon(df, islem_maliyeti=0.001):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / (d["Bakir"] * d["Bitcoin"])
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d = d.dropna().copy()

    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows, equity, btc_pct_list, alt_pct_list, cost_list = [], [], [], [], []
    btc_gun = alt_gun = 0
    max_port = 10000.0
    max_dd = 0.0
    toplam_maliyet = 0.0

    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        bp, ap = float(row["Bitcoin"]), float(row["Altin"])
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(r, s10, s50)

        port_val = cash + btc_qty * bp + alt_qty * ap
        changed = (prev_regime is None) or (isim != prev_regime)
        islem_maliyeti_tl = 0.0

        if changed:
            islem_maliyeti_tl = port_val * islem_maliyeti
            toplam_maliyet += islem_maliyeti_tl
            port_val_net = port_val - islem_maliyeti_tl

            if isim == "Güçlü Boğa":
                btc_qty = port_val_net / bp
                alt_qty = cash = 0.0
            elif isim == "Boğa + Düzeltme":
                btc_qty = (port_val_net * 0.5) / bp
                alt_qty = (port_val_net * 0.5) / ap
                cash = 0.0
            else:
                alt_qty = port_val_net / ap
                btc_qty = cash = 0.0

            port_after = cash + btc_qty * bp + alt_qty * ap
            trade_rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Geçiş": f"{prev_regime or 'Başlangıç'} → {isim}",
                "Rejim": etiket,
                "Dağılım": f"BTC %{t_btc} · Altın %{t_alt}",
                "Brüt Portföy": round(port_val, 0),
                "İşlem Maliyeti": round(islem_maliyeti_tl, 0),
                "Net Portföy": round(port_after, 0),
                "Getiri": round((port_after / 10000.0 - 1) * 100, 1),
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
        cost_list.append(islem_maliyeti_tl)

    d["Portfoy"] = equity
    d["BtcPct"] = btc_pct_list
    d["AltinPct"] = alt_pct_list
    d["IslemMaliyeti"] = cost_list

    stats = {
        "islem_sayisi": len(trade_rows),
        "btc_gun": btc_gun,
        "alt_gun": alt_gun,
        "max_dd": round(max_dd, 1),
        "toplam_gun": len(d),
        "toplam_maliyet": round(toplam_maliyet, 0),
        "islem_maliyeti_orani": islem_maliyeti,
    }
    return d, pd.DataFrame(trade_rows), stats

# ── 7/24 ARKA PLAN SCHEDULER ─────────────────────────────────────────────────
def rejim_kontrol_ve_bildir():
    try:
        symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
        df = yf.download(list(symbols.keys()), period="60d", interval="1d", auto_adjust=False, progress=False)
        if df.empty:
            return

        if isinstance(df.columns, pd.MultiIndex):
            df = df["Close"] if "Close" in df.columns.get_level_values(0) else df
        elif "Close" in df.columns:
            df = df["Close"]

        df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
        df = df[["Altin", "Bakir", "Bitcoin"]].ffill().bfill().dropna()
        if len(df) < 52:
            return

        df["Rasyo"] = df["Altin"] / (df["Bakir"] * df["Bitcoin"])
        df["SMA10"] = df["Rasyo"].rolling(10).mean()
        df["SMA50"] = df["Rasyo"].rolling(50).mean()
        df = df.dropna()

        last = df.iloc[-1]
        r, s10, s50 = float(last["Rasyo"]), float(last["SMA10"]), float(last["SMA50"])
        btc_fiyat = float(last["Bitcoin"])
        alt_fiyat = float(last["Altin"])

        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(r, s10, s50)

        state = load_state()
        prev = state.get("rejim", "")

        if prev and prev != etiket:
            mesaj = (
                f"🚨 *REJİM DEĞİŞİMİ ALARMI* 🚨\n\n"
                f"*{prev}*\n⬇️\n*{etiket}*\n\n"
                f"🪙 BTC: {fmt_usd(btc_fiyat)}\n"
                f"🥇 Altın: {fmt_usd(alt_fiyat)}\n"
                f"💼 Yeni Pozisyon: BTC %{t_btc} · Altın %{t_alt}\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"},
                    timeout=10
                )
                state["son_telegram"] = "✅ Gönderildi" if r.ok else f"❌ {r.json().get('description', 'Hata')}"
            except Exception as te:
                state["son_telegram"] = f"❌ Bağlantı hatası: {te}"

        state.update({
            "rejim": etiket,
            "son_kontrol": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "btc_fiyat": round(btc_fiyat, 0),
            "alt_fiyat": round(alt_fiyat, 0),
        })
        save_state(state)

    except Exception:
        pass

# Scheduler — Streamlit her worker'da bir kez başlatılır
if SCHEDULER_OK and "scheduler_started" not in st.session_state:
    _sch = BackgroundScheduler(timezone="Europe/Istanbul")
    _sch.add_job(rejim_kontrol_ve_bildir, "interval",
                 minutes=KONTROL_ARALIK, id="rejim_kontrol",
                 replace_existing=True, next_run_time=datetime.now())
    _sch.start()
    st.session_state["scheduler_started"] = True

# ══════════════════════════════════════════════════════════════════════════════
# ANA UYGULAMA
# ══════════════════════════════════════════════════════════════════════════════
try:
    raw = verileri_getir()
    if raw.empty or len(raw) < 60:
        st.error("Veri yeterli büyüklükte değil.")
        st.stop()

    for col in ["Altin", "Bakir", "Bitcoin"]:
        if col not in raw.columns:
            st.error(f"'{col}' verisi çekilemedi. Lütfen sayfayı yenileyin.")
            st.stop()
        if raw[col].isna().all():
            st.error(f"'{col}' verisi tamamen boş. Lütfen sayfayı yenileyin.")
            st.stop()

    data, trade_log, stats = backtest_rotasyon(raw, islem_maliyeti=0.001)

    last = data.iloc[-1]
    btc_fiyat = float(last["Bitcoin"])
    alt_fiyat = float(last["Altin"])
    son_rasyo = float(last["Rasyo"])
    sma10 = float(last["SMA10"])
    sma50 = float(last["SMA50"])
    kisa_bull = son_rasyo < sma10
    makro_bull = son_rasyo < sma50

    isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = rejim_tespit(son_rasyo, sma10, sma50)

    data["BH_BTC"] = (10000.0 / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
    data["BH_Altin"] = (10000.0 / float(data["Altin"].iloc[0])) * data["Altin"]

    rot_son = float(data["Portfoy"].iloc[-1])
    rot_kazanc = (rot_son / 10000.0 - 1) * 100
    bh_btc_son = float(data["BH_BTC"].iloc[-1])
    bh_btc_k = (bh_btc_son / 10000.0 - 1) * 100
    bh_alt_son = float(data["BH_Altin"].iloc[-1])
    bh_alt_k = (bh_alt_son / 10000.0 - 1) * 100

    btc_degisim = (btc_fiyat / float(data["Bitcoin"].iloc[-2]) - 1) * 100 if len(data) >= 2 else 0.0
    alt_degisim = (alt_fiyat / float(data["Altin"].iloc[-2]) - 1) * 100 if len(data) >= 2 else 0.0

    # ── 1. METRİK KARTLARI ──────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin",      fmt_usd(btc_fiyat),  fmt_pct(btc_degisim) + " son gün")
    c2.metric("Altın",        fmt_usd(alt_fiyat),  fmt_pct(alt_degisim) + " son gün")
    c3.metric("8Y Rotasyon",  fmt_usd(rot_son),    fmt_pct(rot_kazanc))
    c4.metric("BTC Al-Tut",   fmt_usd(bh_btc_son), fmt_pct(bh_btc_k))
    c5.metric("Altın Al-Tut", fmt_usd(bh_alt_son), fmt_pct(bh_alt_k))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 2. REJİM BANNER ─────────────────────────────────────────────────────
    st.markdown(f"""
<div class="lk-regime lk-regime-{rejim_kodu}">
    <span>{rejim_etiketi}</span>
    <span style="font-weight:400; font-size:12px; color:#7C8595">{rejim_aciklama}</span>
    <span style="margin-left:auto; font-size:13px;">
        Şu an: <b style="color:#F0B90B">BTC %{btc_pct_now}</b>
        &nbsp;·&nbsp;
        <b style="color:#E5C07B">Altın %{alt_pct_now}</b>
    </span>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    fark = rot_son - bh_btc_son
    if fark >= 0:
        st.success(f"Rotasyon BTC al-tutun **{fmt_usd(fark)}** önünde  ·  Rotasyon {fmt_pct(rot_kazanc)}  vs  BTC al-tut {fmt_pct(bh_btc_k)}  vs  Altın al-tut {fmt_pct(bh_alt_k)}")
    else:
        st.warning(f"Rotasyon BTC al-tutun **{fmt_usd(abs(fark))}** gerisinde  ·  Rotasyon {fmt_pct(rot_kazanc)}  vs  BTC al-tut {fmt_pct(bh_btc_k)}  vs  Altın al-tut {fmt_pct(bh_alt_k)}")

    # ── 3. PERFORMANS İSTATİSTİKLERİ ────────────────────────────────────────
    st.markdown('<div class="lk-section">Strateji Performans İstatistikleri</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("Toplam İşlem", str(stats["islem_sayisi"]), "rejim geçişi")
    s2.metric("BTC'de Geçen Süre", f"{stats['btc_gun']} gün", fmt_pct(stats['btc_gun'] / stats['toplam_gun'] * 100))
    s3.metric("Altın'da Geçen Süre", f"{stats['alt_gun']} gün", fmt_pct(stats['alt_gun'] / stats['toplam_gun'] * 100))
    s4.metric("Maks. Drawdown", fmt_pct(stats["max_dd"]))
    s5.metric("Rotasyon Avantajı", fmt_usd(rot_son - bh_btc_son))
    s6.metric("Toplam Maliyet", fmt_usd(stats.get("toplam_maliyet", 0)))

    # ── 4. LİKİDİTE RASYO GRAFİĞİ ──────────────────────────────────────────
    st.markdown('<div class="lk-section">Likidite Rasyosu · SMA10 · SMA50 · BTC Fiyatı</div>', unsafe_allow_html=True)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=data.index, y=data["Rasyo"],
        name="Rasyo", line=dict(color=SUB, width=1.0), opacity=0.7))

    data["Renk10"] = (data["Rasyo"] < data["SMA10"]).map({True: "#4ADE80", False: "#F87171"})
    for _, grp in data.groupby((data["Renk10"] != data["Renk10"].shift()).cumsum()):
        fig1.add_trace(go.Scatter(x=grp.index, y=grp["SMA10"], mode="lines",
            line=dict(color=grp["Renk10"].iloc[0], width=1.5, dash="dot"),
            showlegend=False))

    data["Renk50"] = (data["Rasyo"] < data["SMA50"]).map({True: "#4ADE80", False: "#F87171"})
    for _, grp in data.groupby((data["Renk50"] != data["Renk50"].shift()).cumsum()):
        fig1.add_trace(go.Scatter(x=grp.index, y=grp["SMA50"], mode="lines",
            line=dict(color=grp["Renk50"].iloc[0], width=2.5),
            showlegend=False))

    fig1.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"],
        name="BTC Fiyatı", line=dict(color="#F0B90B", width=1.2, dash="dot"),
        yaxis="y2"))

    for lbl, col, dsh in [("SMA50 Boğa","#4ADE80","solid"),("SMA50 Ayı","#F87171","solid"),
                          ("SMA10 Boğa","#4ADE80","dot"),  ("SMA10 Ayı","#F87171","dot")]:
        fig1.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=lbl,
            line=dict(color=col, dash=dsh, width=2)))

    fig1.update_layout(
        height=540, template=PLOTTEM,
        paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=BORDER),
        yaxis=dict(title="Rasyo", gridcolor=BORDER,
                   title_font=dict(color=SUB), tickfont=dict(color=SUB)),
        yaxis2=dict(title="BTC (USD)", overlaying="y", side="right",
                    title_font=dict(color="#F0B90B"), tickfont=dict(color="#F0B90B"),
                    gridcolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig1, use_container_width=True)

    # ── 5. PORTFÖY KARŞILAŞTIRMA ────────────────────────────────────────────
    st.markdown('<div class="lk-section">Portföy Karşılaştırma · Rotasyon vs BTC Al-Tut vs Altın Al-Tut</div>', unsafe_allow_html=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=data.index, y=data["Portfoy"],
        name="BTC+Altın Rotasyon", line=dict(color="#6FE3B5", width=2.5)))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"],
        name="BTC Al-Tut", line=dict(color="#F0B90B", width=1.5, dash="dot")))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"],
        name="Altın Al-Tut", line=dict(color="#E5C07B", width=1.5, dash="dash")))
    fig2.update_layout(
        height=360, template=PLOTTEM,
        paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=BORDER),
        yaxis=dict(title="Portföy Değeri (USD)", gridcolor=BORDER,
                   title_font=dict(color=SUB), tickfont=dict(color=SUB)),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig2, use_container_width=True)

    # ── 6. POZİSYON DAĞILIMI ────────────────────────────────────────────────
    st.markdown('<div class="lk-section">Portföy Dağılımı · BTC vs Altın Ağırlığı</div>', unsafe_allow_html=True)

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=data.index, y=data["BtcPct"],
        name="BTC %", line=dict(color="#F0B90B", width=1.2),
        fill="tozeroy", fillcolor="rgba(240,185,11,0.15)"))
    fig3.add_trace(go.Scatter(x=data.index, y=data["AltinPct"],
        name="Altın %", line=dict(color="#E5C07B", width=1.2),
        fill="tozeroy", fillcolor="rgba(229,192,123,0.08)"))
    fig3.update_layout(
        height=200, template=PLOTTEM,
        paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=BORDER),
        yaxis=dict(title="%", gridcolor=BORDER, range=[0,110],
                   title_font=dict(color=SUB), tickfont=dict(color=SUB)),
        legend=dict(orientation="h", y=1.08, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig3, use_container_width=True)

    # ── 7. İŞLEM GÜNLÜĞÜ ────────────────────────────────────────────────────
    st.markdown('<div class="lk-section">8 Yıllık İşlem Günlüğü</div>', unsafe_allow_html=True)

    def renk_satir(row):
        g = str(row.get("Geçiş", ""))
        if "Güçlü Boğa" in g and "→ Güçlü Boğa" in g:
            return ["background-color:rgba(34,197,94,0.12)"] * len(row)
        elif "→ Boğa + Düzeltme" in g:
            return ["background-color:rgba(234,179,8,0.10)"] * len(row)
        elif "Altın" in g or "Ayı" in g:
            return ["background-color:rgba(239,68,68,0.10)"] * len(row)
        return [""] * len(row)

    st.dataframe(trade_log.style.apply(renk_satir, axis=1),
                 use_container_width=True, hide_index=True)

    # ── 8. OTOMATİK ALARM DURUMU ────────────────────────────────────────────
    st.markdown('<div class="lk-section">Otomatik Alarm Sistemi · 7/24</div>', unsafe_allow_html=True)

    state = load_state()
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Kontrol Sıklığı", f"Her {KONTROL_ARALIK} dakika", "✅ Aktif" if SCHEDULER_OK else "⚠️ APScheduler eksik")
    a2.metric("Son Kontrol", state.get("son_kontrol", "Bekleniyor"), f"BTC {fmt_usd(state['btc_fiyat'])}" if "btc_fiyat" in state else "")
    a3.metric("İzlenen Rejim", state.get("rejim", "—"), "Değişince alarm")
    a4.metric("Son Telegram", state.get("son_telegram", "Henüz alarm gönderilmedi"), "")

    if not SCHEDULER_OK:
        st.warning("APScheduler kurulu değil — `requirements.txt`'e `apscheduler>=3.10.4` ekleyin.")

    # ── 9. YAPAY ZEKA YORUMU ────────────────────────────────────────────────
    st.markdown('<div class="lk-section">Yapay Zeka Piyasa Yorumu</div>', unsafe_allow_html=True)

    if not trade_log.empty:
        en_iyi = trade_log.loc[trade_log["Getiri"].idxmax()]
        en_kotu = trade_log.loc[trade_log["Getiri"].idxmin()]
        trade_ozet = (
            f"8 yılda toplam {len(trade_log)} rejim geçişi yaşandı.\n"
            f"En yüksek getiri: {en_iyi['Tarih']} tarihinde {en_iyi['Geçiş']} geçişiyle portföy {fmt_usd(en_iyi['Net Portföy'])} oldu (%{en_iyi['Getiri']:+.1f}).\n"
            f"En düşük getiri: {en_kotu['Tarih']} tarihinde {en_kotu['Geçiş']} geçişiyle portföy {fmt_usd(en_kotu['Net Portföy'])} oldu (%{en_kotu['Getiri']:+.1f}).\n"
            f"Son işlem: {trade_log.iloc[-1]['Tarih']} — {trade_log.iloc[-1]['Geçiş']}."
        )
    else:
        trade_ozet = "İşlem günlüğü boş."

    if GEMINI_KEY:
        with st.spinner("Piyasa verileri yorumlanıyor..."):
            yorum = gemini_yorum_cache(
                round(btc_fiyat / 500) * 500,
                rejim_etiketi, rot_kazanc, bh_btc_k, bh_alt_k,
                kisa_bull, makro_bull)
        if yorum:
            st.markdown(f'<div class="lk-ai-box">{yorum}</div>', unsafe_allow_html=True)
        else:
            st.info("Otomatik yorum şu an alınamadı (rate limit). 30 dakika sonra yenilenir.")
    else:
        st.info("Otomatik yorum için `GEMINI_API_KEY` ekleyin — Ücretsiz: aistudio.google.com")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    soru = st.text_input("", placeholder="İşlem günlüğü, rejim veya strateji hakkında bir soru sorun...", label_visibility="collapsed")
    if soru and GEMINI_KEY:
        with st.spinner("Yanıt hazırlanıyor..."):
            yanit = gemini_api(f"""
Sen bir piyasa analisti danışmanısın. Aşağıdaki verilere dayanarak soruyu yanıtla.
Sıradan bir yatırımcıya sade Türkçe, kısa ve net yanıt ver. Teknik jargon kullanma.

MEVCUT DURUM:
- BTC: {fmt_usd(btc_fiyat)} | Altın: {fmt_usd(alt_fiyat)}
- Rejim: {rejim_etiketi}
- Kısa vade: {"Boğa" if kisa_bull else "Ayı"} | Uzun vade: {"Boğa" if makro_bull else "Ayı"}
- Şu an pozisyon: BTC %{btc_pct_now} · Altın %{alt_pct_now}

PORTFÖY PERFORMANSI:
- 8Y Rotasyon: {fmt_pct(rot_kazanc)} ({fmt_usd(rot_son)})
- BTC al-tut: {fmt_pct(bh_btc_k)} ({fmt_usd(bh_btc_son)})
- Altın al-tut: {fmt_pct(bh_alt_k)} ({fmt_usd(bh_alt_son)})
- Maks. Drawdown: {fmt_pct(stats['max_dd'])}
- BTC'de geçen süre: {stats['btc_gun']} gün | Altın'da: {stats['alt_gun']} gün
- Toplam işlem maliyeti: {fmt_usd(stats.get('toplam_maliyet', 0))}

İŞLEM GEÇMİŞİ ÖZETİ:
{trade_ozet}

Soru: {soru}
""")
            if yanit:
                st.markdown(f'<div class="lk-ai-box">{yanit}</div>', unsafe_allow_html=True)
    elif soru and not GEMINI_KEY:
        st.info("`GEMINI_API_KEY` olmadan soru yanıtlanamaz.")

    # ── 10. MANUEL TELEGRAM ──────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button("📲 Güncel Durumu Telegram'a Gönder"):
        if not TOKEN:
            st.error("TELEGRAM_TOKEN eksik — Streamlit secrets'a ekleyin.")
        elif not CHAT_ID:
            st.error("TELEGRAM_CHAT_ID eksik — Streamlit secrets'a ekleyin.")
        else:
            rapor = (
                f"◆ *LİKİDİTE KOMPOZİT PANELİ* ◆\n\n"
                f"🪙 BTC: {fmt_usd(btc_fiyat)} ({fmt_pct(btc_degisim)} gün)\n"
                f"🥇 Altın: {fmt_usd(alt_fiyat)} ({fmt_pct(alt_degisim)} gün)\n\n"
                f"📊 Rejim: *{rejim_etiketi}*\n"
                f"  • Kısa Vade: {'🟢 Boğa' if kisa_bull else '🔴 Ayı'}\n"
                f"  • Uzun Vade: {'🟢 Boğa' if makro_bull else '🔴 Ayı'}\n\n"
                f"💼 Pozisyon: BTC %{btc_pct_now} · Altın %{alt_pct_now}\n\n"
                f"📈 8Y Rotasyon:   {fmt_usd(rot_son)} ({fmt_pct(rot_kazanc)})\n"
                f"₿  BTC Al-Tut:   {fmt_usd(bh_btc_son)} ({fmt_pct(bh_btc_k)})\n"
                f"🥇 Altın Al-Tut:  {fmt_usd(bh_alt_son)} ({fmt_pct(bh_alt_k)})\n\n"
                f"💸 Toplam İşlem Maliyeti: {fmt_usd(stats.get('toplam_maliyet', 0))}\n\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": rapor, "parse_mode": "Markdown"},
                    timeout=10
                )
                if r.ok:
                    st.success("Telegram'a gönderildi.")
                else:
                    hata = r.json().get("description", r.text)
                    st.error(f"Telegram hatası: {hata}")
            except Exception as e:
                st.error(f"Bağlantı hatası: {e}")

except Exception as e:
    import traceback
    st.error(f"Genel hata: {e}")
    st.code(traceback.format_exc())
