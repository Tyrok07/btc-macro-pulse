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

st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"

TEMA = "dark"

if TEMA == "dark":
    BG = "#0B0E14"
    CARD = "#131722"
    BORDER = "#1E2430"
    BORDER2 = "#2A3140"
    TEXT = "#E6E9EF"
    TEXT2 = "#F2F4F8"
    SUB = "#7C8595"
    MUTEDTX = "#C8CDD8"
    PLOTBG = "#0B0E14"
    PLOTTEM = "plotly_dark"
else:
    BG = "#F4F6FA"
    CARD = "#FFFFFF"
    BORDER = "#E2E6EF"
    BORDER2 = "#CBD2E0"
    TEXT = "#1A1D23"
    TEXT2 = "#111318"
    SUB = "#6B7280"
    MUTEDTX = "#374151"
    PLOTBG = "#FFFFFF"
    PLOTTEM = "plotly_white"

st.markdown(
    f"""
    <style>
    html, body, .stApp {{
        background: {BG};
        color: {TEXT};
        font-family: Inter, sans-serif;
    }}
    .lk-header {{
        padding: 26px 4px 18px 4px;
        border-bottom: 1px solid {BORDER};
        margin-bottom: 22px;
    }}
    .lk-eyebrow {{
        font-family: JetBrains Mono, monospace;
        font-size: 11px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #6FE3B5;
        margin-bottom: 6px;
    }}
    .lk-title {{
        font-size: 30px;
        font-weight: 700;
        color: {TEXT2};
        margin: 0;
        letter-spacing: -0.01em;
    }}
    .lk-subtitle {{
        font-size: 14px;
        color: {SUB};
        margin-top: 5px;
    }}
    .lk-regime {{
        border-radius: 12px;
        padding: 13px 18px;
        border: 1px solid;
        font-family: JetBrains Mono, monospace;
        font-weight: 700;
        font-size: 13px;
        line-height: 1.6;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }}
    .lk-regime-strong-on {{
        background: rgba(34,197,94,0.12);
        border-color: rgba(34,197,94,0.5);
        color: #4ADE80;
    }}
    .lk-regime-weak-on {{
        background: rgba(234,179,8,0.10);
        border-color: rgba(234,179,8,0.4);
        color: #F59E0B;
    }}
    .lk-regime-weak-off {{
        background: rgba(249,115,22,0.10);
        border-color: rgba(249,115,22,0.4);
        color: #F97316;
    }}
    .lk-regime-strong-off {{
        background: rgba(239,68,68,0.10);
        border-color: rgba(239,68,68,0.4);
        color: #EF4444;
    }}
    .lk-section {{
        font-size: 15px;
        font-weight: 600;
        color: {TEXT2};
        margin: 28px 0 12px 0;
        padding-left: 10px;
        border-left: 3px solid #6FE3B5;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="lk-header">
      <div class="lk-eyebrow">XAUUSD · XCUUSD · BTCUSD Likidite Kompoziti · 8 Yıllık Analiz</div>
      <div class="lk-title">Süper Kompozit Likidite Paneli</div>
      <div class="lk-subtitle">Altın · Bakır · Bitcoin rasyosu üzerinden küresel likidite yönünü ve fırsatları takip et</div>
    </div>
    """,
    unsafe_allow_html=True,
)

GEMINI_API_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TELEGRAM_TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
TELEGRAM_CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()
KONTROL_ARALIK = 15

def fmt_pct(x):
    return f"{x:.1f}%"

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
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "Markdown"},
            timeout=10,
        )
        return r.ok
    except Exception:
        return False

@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {
        "GC=F": "Altin",
        "SI=F": "Gumus",
        "HG=F": "Bakir",
        "^DXY": "DXY",
        "BTC-USD": "Bitcoin",
    }

    df = yf.download(
        list(symbols.keys()),
        period="8y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="ticker",
    )

    if df.empty:
        return pd.DataFrame()

    out = pd.DataFrame(index=df.index)

    if isinstance(df.columns, pd.MultiIndex):
        for sym, name in symbols.items():
            try:
                if sym in df.columns.get_level_values(0):
                    tmp = df[sym]
                    if isinstance(tmp, pd.DataFrame):
                        if "Close" in tmp.columns:
                            out[name] = tmp["Close"]
                        elif "close" in tmp.columns:
                            out[name] = tmp["close"]
                elif sym in df.columns.get_level_values(1):
                    try:
                        out[name] = df.xs("Close", axis=1, level=1)[sym]
                    except Exception:
                        pass
            except Exception:
                pass
    else:
        if "Close" in df.columns:
            out["Bitcoin"] = df["Close"]

    try:
        m2 = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL")
        m2.columns = ["Date", "M2"]
        m2["Date"] = pd.to_datetime(m2["Date"])
        m2 = m2.set_index("Date").resample("D").ffill()
        out = out.join(m2, how="left")
    except Exception:
        pass

    out = out[[c for c in ["Altin", "Gumus", "Bakir", "DXY", "Bitcoin", "M2"] if c in out.columns]]
    return out.ffill().bfill()

def rejimtespit(r, s10, s50, dxy, dxy_ma, m2, m2_ma):
    metal_risk_on = r < s10
    dxy_weak = dxy < dxy_ma
    m2_expanding = m2 > m2_ma
    skor = int(metal_risk_on) + int(dxy_weak) + int(m2_expanding)

    if skor == 3:
        return "Güçlü Boğa", 100, 0, "strong-on", "GÜÇLÜ BOĞA", "Üç sinyal de BTC lehine"
    elif skor == 2:
        return "Hazır Boğa", 75, 25, "weak-on", "HAZIR BOĞA", "İki sinyal olumlu, ortam destekleyici"
    elif skor == 1:
        return "Kararsız", 50, 50, "weak-off", "DİKKAT", "Sadece bir sinyal olumlu, bekle-gör"
    else:
        return "Güçlü Ayı", 0, 100, "strong-off", "GÜÇLÜ AYI", "Üç sinyal de BTC aleyhine"

def backtest_rotasyon(df):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / d["Bakir"]
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d["DXY_MA"] = d["DXY"].rolling(20).mean()
    d["M2_MA"] = d["M2"].rolling(10).mean()
    d = d.dropna().copy()

    cash = 10000.0
    btc_qty = 0.0
    alt_qty = 0.0
    prev_regime = None
    rows = []
    equity = []
    btc_pct_list = []
    alt_pct_list = []

    btc_gun = 0
    alt_gun = 0
    max_port = 10000.0
    max_dd = 0.0

    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        dxy, dxy_ma = row["DXY"], row["DXY_MA"]
        m2, m2_ma = row["M2"], row["M2_MA"]

        isim, tbtc, talt, kod, etiket, aciklama = rejimtespit(r, s10, s50, dxy, dxy_ma, m2, m2_ma)

        port_val = cash + btc_qty * float(row["Bitcoin"]) + alt_qty * float(row["Altin"])
        changed = prev_regime is None or isim != prev_regime

        if changed:
            if isim == "Güçlü Boğa":
                btc_qty = port_val / float(row["Bitcoin"])
                alt_qty = 0.0
                cash = 0.0
            elif isim == "Hazır Boğa":
                btc_qty = (port_val * 0.75) / float(row["Bitcoin"])
                alt_qty = (port_val * 0.25) / float(row["Altin"])
                cash = 0.0
            elif isim == "Kararsız":
                btc_qty = 0.0
                alt_qty = 0.0
                cash = port_val
            else:
                btc_qty = 0.0
                alt_qty = port_val / float(row["Altin"])
                cash = 0.0

        port_now = cash + btc_qty * float(row["Bitcoin"]) + alt_qty * float(row["Altin"])
        rows.append({
            "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
            "Geçiş": f"{prev_regime or 'Başlangıç'} -> {isim}",
            "Rejim": etiket,
            "Dağılım": f"BTC {tbtc}% / Altın {talt}%",
            "Portföy": round(port_now, 2),
            "Getiri": round((port_now / 10000.0 - 1) * 100, 2),
        })

        prev_regime = isim
        max_port = max(max_port, port_now)
        dd = (port_now - max_port) / max_port * 100
        max_dd = min(max_dd, dd)

        if tbtc == 100:
            btc_gun += 1
        if talt == 100:
            alt_gun += 1

        equity.append(port_now)
        btc_pct_list.append(tbtc)
        alt_pct_list.append(talt)

    d["Portföy"] = equity
    d["BtcPct"] = btc_pct_list
    d["AltinPct"] = alt_pct_list

    stats = {
        "islem_sayisi": len(rows),
        "btc_gun": btc_gun,
        "alt_gun": alt_gun,
        "max_dd": round(max_dd, 1),
        "toplam_gun": len(d),
    }
    return d, pd.DataFrame(rows), stats

def rejim_kontrol_ve_bildir():
    try:
        raw = verileri_getir()
        if raw.empty or len(raw) < 60:
            return
        raw = raw.dropna().copy()
        raw["Rasyo"] = raw["Altin"] / raw["Bakir"]
        raw["SMA10"] = raw["Rasyo"].rolling(10).mean()
        raw["SMA50"] = raw["Rasyo"].rolling(50).mean()
        raw["DXY_MA"] = raw["DXY"].rolling(20).mean()
        raw["M2_MA"] = raw["M2"].rolling(10).mean()
        raw = raw.dropna().copy()
        last = raw.iloc[-1]

        isim, tbtc, talt, kod, etiket, aciklama = rejimtespit(
            float(last["Rasyo"]),
            float(last["SMA10"]),
            float(last["SMA50"]),
            float(last["DXY"]),
            float(last["DXY_MA"]),
            float(last["M2"]),
            float(last["M2_MA"]),
        )

        state = load_state()
        prev = state.get("rejim")
        if prev and prev != etiket:
            mesaj = (
                f"*REJİM DEĞİŞİM ALARMI*\n"
                f"{prev} -> {etiket}\n"
                f"BTC: {float(last['Bitcoin']):.0f}\n"
                f"Altın: {float(last['Altin']):.0f}\n"
                f"Yeni Pozisyon: BTC {tbtc}% / Altın {talt}%"
            )
            ok = telegram_gonder(mesaj)
            state["son_telegram"] = datetime.now().strftime("%d.%m.%Y %H:%M") if ok else state.get("son_telegram", "")
        state["rejim"] = etiket
        state["son_kontrol"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        save_state(state)
    except Exception:
        pass

raw = verileri_getir()
if raw.empty or len(raw) < 60:
    st.error("Veri yeterli büyüklükte değil.")
    st.stop()

for col in ["Altin", "Bakir", "Bitcoin", "DXY", "M2"]:
    if col not in raw.columns:
        st.error(f"{col} verisi eklenemedi. Lütfen sayfayı yenileyin.")
        st.stop()
    if raw[col].isna().all():
        st.error(f"{col} verisi tamamen boş. Lütfen sayfayı yenileyin.")
        st.stop()

data, tradelog, stats = backtest_rotasyon(raw)

data["Rasyo"] = data["Altin"] / data["Bakir"]
data["SMA10"] = data["Rasyo"].rolling(10).mean()
data["SMA50"] = data["Rasyo"].rolling(50).mean()
data["DXY_MA"] = data["DXY"].rolling(20).mean()
data["M2_MA"] = data["M2"].rolling(10).mean()
data = data.dropna().copy()

last = data.iloc[-1]
isim, btcpctnow, altpctnow, rejim_kodu, rejim_etiketi, rejim_aciklama = rejimtespit(
    float(last["Rasyo"]),
    float(last["SMA10"]),
    float(last["SMA50"]),
    float(last["DXY"]),
    float(last["DXY_MA"]),
    float(last["M2"]),
    float(last["M2_MA"]),
)

btcfiyat = float(last["Bitcoin"])
altfiyat = float(last["Altin"])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Bitcoin", fmt_usd(btcfiyat))
c2.metric("Altın", fmt_usd(altfiyat))
c3.metric("8Y Rotasyon", fmt_usd(float(data["Portföy"].iloc[-1])))
c4.metric("BTC Al-Tut", fmt_usd(float(10000.0 * btcfiyat / float(data["Bitcoin"].iloc[0]))))
c5.metric("Altın Al-Tut", fmt_usd(float(10000.0 * altfiyat / float(data["Altin"].iloc[0]))))

st.markdown(
    f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
      <span>{rejim_etiketi}</span>
      <span style="font-weight:400; font-size:12px; color:#7C8595">{rejim_aciklama}</span>
      <span style="margin-left:auto; font-size:13px">
        u an <b style="color:#F0B90B">BTC {btcpctnow}%</b> &nbsp;&nbsp;
        <b style="color:#E5C07B">Altın {altpctnow}%</b>
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)

fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=data.index, y=data["Rasyo"], name="Rasyo", line=dict(color=SUB, width=1.0), opacity=0.7))
fig1.add_trace(go.Scatter(x=data.index, y=data["SMA10"], name="SMA10", line=dict(color="#4ADE80", width=1.5, dash="dot")))
fig1.add_trace(go.Scatter(x=data.index, y=data["SMA50"], name="SMA50", line=dict(color="#F87171", width=2.5)))
fig1.add_trace(go.Scatter(x=data.index, y=data["Bitcoin"], name="BTC Fiyat", line=dict(color="#F0B90B", width=1.2, dash="dash"), yaxis="y2"))
fig1.update_layout(
    height=540,
    template=PLOTTEM,
    paper_bgcolor=PLOTBG,
    plot_bgcolor=PLOTBG,
    font=dict(family="Inter", color=TEXT),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor=BORDER),
    yaxis=dict(title="Rasyo", gridcolor=BORDER),
    yaxis2=dict(title="BTC USD", overlaying="y", side="right", titlefont=dict(color="#F0B90B"), tickfont=dict(color="#F0B90B"), gridcolor="rgba(0,0,0,0)"),
    legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig1, use_container_width=True)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=data.index, y=data["Portföy"], name="BTC+Altın Rotasyon", line=dict(color="#6FE3B5", width=2.5)))
fig2.update_layout(
    height=360,
    template=PLOTTEM,
    paper_bgcolor=PLOTBG,
    plot_bgcolor=PLOTBG,
    font=dict(family="Inter", color=TEXT),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor=BORDER),
    yaxis=dict(title="Portföy Değeri USD", gridcolor=BORDER),
    legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
    bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig2, use_container_width=True)

fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=data.index, y=data["BtcPct"], name="BTC", line=dict(color="#F0B90B", width=1.2), fill="tozeroy", fillcolor="rgba(240,185,11,0.15)"))
fig3.add_trace(go.Scatter(x=data.index, y=data["AltinPct"], name="Altın", line=dict(color="#E5C07B", width=1.2), fill="tozeroy", fillcolor="rgba(229,192,123,0.08)"))
fig3.update_layout(
    height=200,
    template=PLOTTEM,
    paper_bgcolor=PLOTBG,
    plot_bgcolor=PLOTBG,
    font=dict(family="Inter", color=TEXT),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor=BORDER),
    yaxis=dict(title="", gridcolor=BORDER, range=[0, 110]),
    legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
    bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig3, use_container_width=True)

st.markdown("### 8 Yıllık İşlem Günlüğü")
st.dataframe(tradelog, use_container_width=True, hide_index=True)

state = load_state()
a1, a2, a3, a4 = st.columns(4)
a1.metric("Kontrol Sıklığı", f"Her {KONTROL_ARALIK} dakika", "Aktif" if SCHEDULER_OK else "APScheduler eksik")
a2.metric("Son Kontrol", state.get("son_kontrol", "Bekleniyor"))
a3.metric("İzlenen Rejim", state.get("rejim", ""))
a4.metric("Son Telegram", state.get("son_telegram", "Henüz alarm gönderilmedi"))

if SCHEDULER_OK and "scheduler_started" not in st.session_state:
    sch = BackgroundScheduler(timezone="Europe/Istanbul")
    sch.add_job(rejim_kontrol_ve_bildir, "interval", minutes=KONTROL_ARALIK, id="rejim_kontrol", replace_existing=True)
    sch.start()
    st.session_state.scheduler_started = True

st.markdown("### Yapay Zeka Piyasa Yorumu")
st.info("Bu sürümde sadece formül mantığı yeni modele çevrildi; mevcut panel yapısı korunmuştur.")

if st.button("Güncel Durumu Telegrama Gönder"):
    if not TELEGRAM_TOKEN:
        st.error("TELEGRAM_TOKEN eksik")
    elif not TELEGRAM_CHAT_ID:
        st.error("TELEGRAM_CHAT_ID eksik")
    else:
        rapor = (
            f"*LKDTE KOMPOZİT PANEL*\n"
            f"BTC {btcfiyat:.0f}\n"
            f"Altın {altfiyat:.0f}\n"
            f"Rejim {rejim_etiketi}\n"
            f"Pozisyon BTC {btcpctnow}% / Altın {altpctnow}%\n"
            f"8Y Rotasyon {float(data['Portföy'].iloc[-1]):.0f}"
        )
        ok = telegram_gonder(rapor)
        if ok:
            st.success("Telegrama gönderildi.")
        else:
            st.error("Telegram hatası")
