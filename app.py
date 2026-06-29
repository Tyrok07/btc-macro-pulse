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
    SCHEDULEROK = True
except ImportError:
    SCHEDULEROK = False

st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="📊")

BASEDIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATEDIR = BASEDIR / "state"
STATEDIR.mkdir(exist_ok=True)
ALERTSTATEFILE = STATEDIR / "alertstate.json"

TEMA = "light"  # SADECE BU SATIRI DEĞİŞTİR

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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
    html, body, .stApp {{ font-family: Inter, sans-serif; }}
    .stApp {{ background: {BG}; color: {TEXT}; }}
    .lk-header {{ padding: 26px 4px 18px 4px; border-bottom: 1px solid {BORDER}; margin-bottom: 22px; }}
    .lk-eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #6FE3B5; margin-bottom: 6px; }}
    .lk-title {{ font-size: 30px; font-weight: 700; color: {TEXT2}; margin: 0; letter-spacing: -0.01em; }}
    .lk-subtitle {{ font-size: 14px; color: {SUB}; margin-top: 5px; }}
    div[data-testid="stMetric"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 14px 16px; }}
    div[data-testid="stMetric"] label {{ color: {SUB} !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.04em; }}
    div[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-size: 20px !important; color: {TEXT2} !important; }}
    .lk-regime {{ border-radius: 12px; padding: 13px 18px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; line-height: 1.6; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
    .lk-regime-strong-on {{ background: rgba(34,197,94,0.12); border-color: rgba(34,197,94,0.5); color: #4ADE80; }}
    .lk-regime-weak-on {{ background: rgba(234,179,8,0.10); border-color: rgba(234,179,8,0.4); color: #F59E0B; }}
    .lk-regime-weak-off {{ background: rgba(249,115,22,0.10); border-color: rgba(249,115,22,0.4); color: #F97316; }}
    .lk-regime-strong-off {{ background: rgba(239,68,68,0.10); border-color: rgba(239,68,68,0.4); color: #EF4444; }}
    .lk-section {{ font-size: 15px; font-weight: 600; color: {TEXT2}; margin: 28px 0 12px 0; padding-left: 10px; border-left: 3px solid #6FE3B5; }}
    .lk-ai-box {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 20px 24px; line-height: 1.80; font-size: 15px; color: {MUTEDTX}; }}
    .stButton button {{ background: {CARD}; border: 1px solid {BORDER2}; color: {TEXT}; border-radius: 8px; font-weight: 500; padding: 8px 18px; }}
    .stButton button:hover {{ border-color: #6FE3B5; color: #6FE3B5; }}
    .stTextInput input {{ background: {CARD}; border: 1px solid {BORDER}; color: {TEXT}; border-radius: 8px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="lk-header">
      <div class="lk-eyebrow">XAUUSD XCUUSD BTCUSD Likidite Kompoziti 8 Yıllık Analiz</div>
      <p class="lk-title">Süper Kompozit Likidite Paneli</p>
      <p class="lk-subtitle">Altın, Bakır, Bitcoin rasyosu üzerinden küresel likidite yönünü ve fırsatları takip et.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

GEMINIKEY = str(st.secrets.get("GEMINIAPIKEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAMTOKEN", "")).strip()
CHATID = str(st.secrets.get("TELEGRAMCHATID", "")).strip()
KONTROLARALIK = 140

def rejimtespit(r, s10, s50):
    if r > s10 and r > s50:
        return "Gl Boa", 100, 0, "strong-on", "GL BOA", "Her iki sinyal BTC lehine. En güçlü alım bölgesi."
    elif r > s50:
        return "Boa Dzeltme", 50, 50, "weak-on", "BOA Ksa Dzeltme", "Büyük trend yukarı. Kısa vadede hafif baskı."
    elif r > s10:
        return "Ay Toparlanma", 0, 100, "weak-off", "AYI Ksa Toparlanma", "Büyük trend aşağı. Kısa vadede geçici rahatlama."
    else:
        return "Gl Ay", 0, 100, "strong-off", "GL AYI", "Her iki sinyal BTC aleyhine. Altın koruma modu."

def fmtpct(x): return f"{x:.1f}%"
def fmtusd(x): return f"${x:,.0f}"
def fmtqty(x): return f"{x:,.6f}"
def fmtint(x): return f"{int(round(x)):,}"

def loadstate():
    try:
        return json.loads(ALERTSTATEFILE.read_text(encoding="utf-8")) if ALERTSTATEFILE.exists() else {}
    except Exception:
        return {}

def savestate(s):
    try:
        ALERTSTATEFILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def telegramgonder(mesaj):
    if not TOKEN or not CHATID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHATID, "text": mesaj, "parse_mode": "Markdown"},
            timeout=10,
        )
        return r.ok
    except Exception:
        return False

@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
    df = yf.download(list(symbols.keys()), period="8y", interval="1d", auto_adjust=False, group_by="column", progress=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            df = df["Close"].copy()
        else:
            df = df.droplevel(0, axis=1)
    elif "Close" in df.columns:
        df = df["Close"]
    df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
    cols = [c for c in ["Altin", "Bakir", "Bitcoin"] if c in df.columns]
    return df[cols].ffill().bfill()

def geminiapiprompt(prompt):
    if not GEMINIKEY:
        return None
    for model in ["gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-2.0-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINIKEY}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if r.status_code == 429:
                continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    return None

def geminiyorumcache(btcr, rejim, rotk, bhbtck, bhaltk, kisabull, makrobull):
    prompt = f"""Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının anlayabileceği sade Türkçe ile 4-6 cümlelik özet yorum yaz. Teknik jargon kullanma. Sonunda tek cümleyle şu an ne yapmalı? önerisi ver.
- Bitcoin: {btcr:,.0f}
- Rejim: {rejim}
- Kısa vade: {"Boğa" if kisabull else "Ayı"}
- Uzun vade: {"Boğa" if makrobull else "Ayı"}
- 8Y Rotasyon kazancı: {rotk:.1f}%
- BTC al-tut kıyas: {bhbtck:.1f}%
- Altın al-tut kıyas: {bhaltk:.1f}%
Sadece yorum metni yaz, madde işareti veya başlık ekleme."""
    return geminiapiprompt(prompt)

def backtestrotasyon(df):
    d = df.copy()
    d["Rasyo"] = d["Altin"] / d["Bakir"]
    d["SMA10"] = d["Rasyo"].rolling(10).mean()
    d["SMA50"] = d["Rasyo"].rolling(50).mean()
    d = d.dropna().copy()

    cash = 10000.0
    btcqty = 0.0
    altqty = 0.0
    bakirqty = 0.0
    prevregime = None
    traderows = []
    equity = []
    btcpctlist = []
    altpctlist = []
    bakirpctlist = []
    btcgun = 0
    altgun = 0
    bakirgun = 0
    maxport = 10000.0
    maxdd = 0.0

    for idx, row in d.iterrows():
        r, s10, s50 = row["Rasyo"], row["SMA10"], row["SMA50"]
        bp, ap, kup = float(row["Bitcoin"]), float(row["Altin"]), float(row["Bakir"])
        isim, tbtc, talt, tbakir, css, etiket, aciklama = rejimtespit(r, s10, s50)

        portval = cash + btcqty * bp + altqty * ap + bakirqty * kup

        changed = prevregime is None or isim != prevregime
        if changed:
            if isim == "Gl Boa":
                btcqty = portval / bp
                altqty = 0.0
                bakirqty = 0.0
                cash = 0.0
            elif isim == "Boa Dzeltme":
                btcqty = (portval * 0.5) / bp
                altqty = (portval * 0.5) / ap
                bakirqty = 0.0
                cash = 0.0
            elif isim == "Ay Toparlanma":
                btcqty = 0.0
                altqty = portval / ap
                bakirqty = 0.0
                cash = 0.0
            else:
                btcqty = 0.0
                altqty = 0.0
                bakirqty = portval / kup
                cash = 0.0

        portnow = cash + btcqty * bp + altqty * ap + bakirqty * kup
        btcpct = (btcqty * bp / portnow * 100) if portnow else 0.0
        altpct = (altqty * ap / portnow * 100) if portnow else 0.0
        bakirpct = (bakirqty * kup / portnow * 100) if portnow else 0.0

        traderows.append({
            "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
            "Geçiş": f"{prevregime or 'Başlangıç'} -> {isim}" if changed else isim,
            "Rejim": etiket,
            "Dahım": f"BTC {tbtc}% | Altın {talt}% | Bakır {tbakir}%",
            "BTC Miktarı": btcqty,
            "Altın Miktarı": altqty,
            "Bakır Miktarı": bakirqty,
            "BTC USD": btcqty * bp,
            "Altın USD": altqty * ap,
            "Bakır USD": bakirqty * kup,
            "Portföy": round(portnow, 2),
            "Getiri": round(portnow / 10000.0 - 1, 4) * 100,
        })

        prevregime = isim
        maxport = max(maxport, portnow)
        dd = (portnow - maxport) / maxport * 100
        maxdd = min(maxdd, dd)

        if tbtc == 100:
            btcgun += 1
        elif talt == 100:
            altgun += 1
        else:
            bakirgun += 1

        equity.append(portnow)
        btcpctlist.append(btcpct)
        altpctlist.append(altpct)
        bakirpctlist.append(bakirpct)

    d["Portföy"] = equity
    d["BtcPct"] = btcpctlist
    d["AltinPct"] = altpctlist
    d["BakirPct"] = bakirpctlist

    stats = {
        "islemsayisi": len(traderows),
        "btcgun": btcgun,
        "altgun": altgun,
        "bakirgun": bakirgun,
        "maxdd": round(maxdd, 1),
        "toplamgun": len(d),
    }
    return d, pd.DataFrame(traderows), stats

def rejimkontrolvebildir():
    try:
        df = verileri_getir().tail(60)
        if df.empty or len(df) < 52:
            return
        data = df.copy()
        data["Rasyo"] = data["Altin"] / data["Bakir"]
        data["SMA10"] = data["Rasyo"].rolling(10).mean()
        data["SMA50"] = data["Rasyo"].rolling(50).mean()
        data = data.dropna()
        last = data.iloc[-1]
        r, s10, s50 = float(last["Rasyo"]), float(last["SMA10"]), float(last["SMA50"])
        btcfiyat = float(last["Bitcoin"])
        altfiyat = float(last["Altin"])
        isim, tbtc, talt, tbakir, css, etiket, aciklama = rejimtespit(r, s10, s50)

        state = loadstate()
        prev = state.get("rejim")
        if prev and prev != etiket:
            mesaj = f"""REJİM DEĞİŞİM ALARMI
Önceki: {prev}
Yeni: {etiket}
BTC: {fmtusd(btcfiyat)}
Altın: {fmtusd(altfiyat)}
Pozisyon: BTC {tbtc}% | Altın {talt}% | Bakır {tbakir}%"""
            telegramgonder(mesaj)

        state.update({"rejim": etiket, "sonkontrol": datetime.now().strftime("%d.%m.%Y %H:%M")})
        savestate(state)
    except Exception:
        pass

if SCHEDULEROK and "schedulerstarted" not in st.session_state:
    sch = BackgroundScheduler(timezone="Europe/Istanbul")
    sch.add_job(rejimkontrolvebildir, "interval", minutes=KONTROLARALIK, id="rejimkontrol", replace_existing=True, next_run_time=datetime.now())
    sch.start()
    st.session_state.schedulerstarted = True

raw = verileri_getir()
if raw.empty or len(raw) < 60:
    st.error("Veri yeterli büyüklükte değil.")
    st.stop()

for col in ["Altin", "Bakir", "Bitcoin"]:
    if col not in raw.columns:
        st.error(f"{col} verisi eklenemedi. Lütfen sayfayı yenileyin.")
        st.stop()
    if raw[col].isna().all():
        st.error(f"{col} verisi tamamen boş. Lütfen sayfayı yenileyin.")
        st.stop()

data, tradelog, stats = backtestrotasyon(raw)

last = data.iloc[-1]
btcfiyat = float(last["Bitcoin"])
altfiyat = float(last["Altin"])
bakirfiyat = float(last["Bakir"])
sonrasyo = float(last["Rasyo"])
sma10 = float(last["SMA10"])
sma50 = float(last["SMA50"])
kisabull = sonrasyo > sma10
makrobull = sonrasyo > sma50

isimnow, btcpctnow, altpctnow, bakirpctnow, rejimkodu, rejimetiketi, rejimaciklama = rejimtespit(sonrasyo, sma10, sma50)

data["BHBTC"] = 10000.0 / float(data["Bitcoin"].iloc[0]) * data["Bitcoin"]
data["BHAltin"] = 10000.0 / float(data["Altin"].iloc[0]) * data["Altin"]
data["BHBakir"] = 10000.0 / float(data["Bakir"].iloc[0]) * data["Bakir"]

rotson = float(data["Portföy"].iloc[-1])
rotkazanc = rotson / 10000.0 - 1
bhbtcson = float(data["BHBTC"].iloc[-1])
bhbtck = bhbtcson / 10000.0 - 1
bhaltson = float(data["BHAltin"].iloc[-1])
bhaltk = bhaltson / 10000.0 - 1
bhbakirson = float(data["BHBakir"].iloc[-1])
bhbakirk = bhbakirson / 10000.0 - 1

btcdegisim = (btcfiyat / float(data["Bitcoin"].iloc[-2]) - 1) * 100 if len(data) >= 2 else 0.0
altdegisim = (altfiyat / float(data["Altin"].iloc[-2]) - 1) * 100 if len(data) >= 2 else 0.0
bakirdegisim = (bakirfiyat / float(data["Bakir"].iloc[-2]) - 1) * 100 if len(data) >= 2 else 0.0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Bitcoin", fmtusd(btcfiyat), fmtpct(btcdegisim))
c2.metric("Altın", fmtusd(altfiyat), fmtpct(altdegisim))
c3.metric("Bakır", fmtusd(bakirfiyat), fmtpct(bakirdegisim))
c4.metric("8Y Rotasyon", fmtusd(rotson), fmtpct(rotkazanc * 100))
c5.metric("BTC Al-Tut", fmtusd(bhbtcson), fmtpct(bhbtck * 100))
c6.metric("Altın Al-Tut", fmtusd(bhaltson), fmtpct(bhaltk * 100))

st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="lk-regime lk-regime-{rejimkodu}">
      <span>{rejimetiketi}</span>
      <span style="font-weight:400; font-size:12px; color:#7C8595;">{rejimaciklama}</span>
      <span style="margin-left:auto; font-size:13px;">u an <b style="color:#F0B90B;">BTC {btcpctnow}%</b> <b style="color:#E5C07B;">Altın {altpctnow}%</b> <b style="color:#60A5FA;">Bakır {bakirpctnow}%</b></span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

st.markdown("### Varlık Dağılımı")
x1, x2, x3, x4, x5 = st.columns(5)
x1.metric("BTC Miktarı", fmtqty(tradelog.iloc[-1]["BTC Miktarı"]), fmtusd(tradelog.iloc[-1]["BTC USD"]))
x2.metric("Altın Ons", fmtqty(tradelog.iloc[-1]["Altın Miktarı"]), fmtusd(tradelog.iloc[-1]["Altın USD"]))
x3.metric("Bakır Miktarı", fmtqty(tradelog.iloc[-1]["Bakır Miktarı"]), fmtusd(tradelog.iloc[-1]["Bakır USD"]))
x4.metric("Toplam Portföy USD", fmtusd(rotson), fmtpct(rotkazanc * 100))
x5.metric("Tahmini işlem adedi", fmtint(stats["islemsayisi"]), f"{stats['btcgun']} BTC / {stats['altgun']} Altın / {stats['bakirgun']} Bakır")

st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

fark = rotson - bhbtcson
if fark >= 0:
    st.success(f"Rotasyon BTC al-tutun {fmtusd(fark)} önünde. Rotasyon {fmtpct(rotkazanc * 100)} vs BTC al-tut {fmtpct(bhbtck * 100)} vs Altın al-tut {fmtpct(bhaltk * 100)}.")
else:
    st.warning(f"Rotasyon BTC al-tutun {fmtusd(abs(fark))} gerisinde. Rotasyon {fmtpct(rotkazanc * 100)} vs BTC al-tut {fmtpct(bhbtck * 100)} vs Altın al-tut {fmtpct(bhaltk * 100)}.")

st.markdown('<div class="lk-section">Strateji Performans İstatistikleri</div>', unsafe_allow_html=True)
s1, s2, s3, s4, s5 = st.columns(5)
s1.metric("Toplam İşlem", str(stats["islemsayisi"]), "rejim geçişi")
s2.metric("BTC'de Geçen Süre", f"{stats['btcgun']} gün", fmtpct(stats["btcgun"] / stats["toplamgun"] * 100))
s3.metric("Altında Geçen Süre", f"{stats['altgun']} gün", fmtpct(stats["altgun"] / stats["toplamgun"] * 100))
s4.metric("Bakırda Geçen Süre", f"{stats['bakirgun']} gün", fmtpct(stats["bakirgun"] / stats["toplamgun"] * 100))
s5.metric("Maks. Drawdown", fmtpct(stats["maxdd"]))

st.markdown('<div class="lk-section">Likidite Rasyosu, SMA10, SMA50, BTC Fiyat</div>', unsafe_allow_html=True)
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
    yaxis2=dict(title="BTC USD", overlaying="y", side="right", titlefont=dict(color="#F0B90B"), tickfont=dict(color="#F0B90B")),
    legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig1, use_container_width=True)

st.markdown('<div class="lk-section">Portföy Karşılaştırma</div>', unsafe_allow_html=True)
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=data.index, y=data["Portföy"], name="BTC-Altın-Bakır Rotasyon", line=dict(color="#6FE3B5", width=2.5)))
fig2.add_trace(go.Scatter(x=data.index, y=data["BHBTC"], name="BTC Al-Tut", line=dict(color="#F0B90B", width=1.5, dash="dot")))
fig2.add_trace(go.Scatter(x=data.index, y=data["BHAltin"], name="Altın Al-Tut", line=dict(color="#E5C07B", width=1.5, dash="dash")))
fig2.add_trace(go.Scatter(x=data.index, y=data["BHBakir"], name="Bakır Al-Tut", line=dict(color="#60A5FA", width=1.5, dash="dashdot")))
fig2.update_layout(
    height=360,
    template=PLOTTEM,
    paper_bgcolor=PLOTBG,
    plot_bgcolor=PLOTBG,
    font=dict(family="Inter", color=TEXT),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor=BORDER),
    yaxis=dict(title="Portföy Değeri USD", gridcolor=BORDER),
    legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig2, use_container_width=True)

st.markdown('<div class="lk-section">Portföy Dağılımı</div>', unsafe_allow_html=True)
fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=data.index, y=data["BtcPct"], name="BTC %", line=dict(color="#F0B90B", width=1.2), fill="tozeroy", fillcolor="rgba(240,185,11,0.15)"))
fig3.add_trace(go.Scatter(x=data.index, y=data["AltinPct"], name="Altın %", line=dict(color="#E5C07B", width=1.2), fill="tozeroy", fillcolor="rgba(229,192,123,0.08)"))
fig3.add_trace(go.Scatter(x=data.index, y=data["BakirPct"], name="Bakır %", line=dict(color="#60A5FA", width=1.2), fill="tozeroy", fillcolor="rgba(96,165,250,0.10)"))
fig3.update_layout(
    height=220,
    template=PLOTTEM,
    paper_bgcolor=PLOTBG,
    plot_bgcolor=PLOTBG,
    font=dict(family="Inter", color=TEXT),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor=BORDER),
    yaxis=dict(title="Yüzde", gridcolor=BORDER, range=[0, 110]),
    legend=dict(orientation="h", y=1.08, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig3, use_container_width=True)

st.markdown('<div class="lk-section">İşlem Günlüğü</div>', unsafe_allow_html=True)

def renksatir(row):
    g = str(row.get("Geçiş", ""))
    if "Gl Boa" in g:
        return ["background-color: rgba(34,197,94,0.12)"] * len(row)
    elif "Boa Dzeltme" in g:
        return ["background-color: rgba(234,179,8,0.10)"] * len(row)
    elif "Altn" in g or "Ay" in g:
        return ["background-color: rgba(239,68,68,0.10)"] * len(row)
    return [""] * len(row)

st.dataframe(tradelog.style.apply(renksatir, axis=1), use_container_width=True, hide_index=True)

st.markdown('<div class="lk-section">Otomatik Alarm Sistemi 7/24</div>', unsafe_allow_html=True)
state = loadstate()
a1, a2, a3, a4 = st.columns(4)
a1.metric("Kontrol Sıklığı", f"Her {KONTROLARALIK} dakika", "Aktif" if SCHEDULEROK else "APScheduler eksik")
a2.metric("Son Kontrol", state.get("sonkontrol", "Bekleniyor"))
a3.metric("İzlenen Rejim", state.get("rejim", ""))
a4.metric("Son Telegram", state.get("sontelegram", "Henüz alarm gönderilmedi"))
if not SCHEDULEROK:
    st.warning("APScheduler kurulu değil. requirements.txt içine apscheduler>=3.10.4 ekleyin.")

st.markdown('<div class="lk-section">Yapay Zeka Piyasa Yorumu</div>', unsafe_allow_html=True)
if GEMINIKEY:
    with st.spinner("Piyasa verileri yorumlanıyor..."):
        yorum = geminiyorumcache(round(btcfiyat), rejimetiketi, rotkazanc * 100, bhbtck * 100, bhaltk * 100, kisabull, makrobull)
        if yorum:
            st.markdown(f'<div class="lk-ai-box">{yorum}</div>', unsafe_allow_html=True)
        else:
            st.info("Otomatik yorum şu an alınamadı.")
else:
    st.info("Otomatik yorum için GEMINIAPIKEY ekleyin.")

st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
soru = st.text_input("", placeholder="İşlem günü, rejim veya strateji hakkında bir soru sorun...", label_visibility="collapsed")
if soru and GEMINIKEY:
    with st.spinner("Yanıt hazırlanıyor..."):
        yanit = geminiapiprompt(f"""Sen bir piyasa analisti danışmansın. Aşağıdaki verilere dayanarak soruyu yanıtla. Sıradan bir yatırımcıya sade Türkçe, kısa ve net yanıt ver. Teknik jargon kullanma.

MEVCUT DURUM
- BTC: {fmtusd(btcfiyat)}
- Altın: {fmtusd(altfiyat)}
- Bakır: {fmtusd(bakirfiyat)}
- Rejim: {rejimetiketi}
- Kısa vade: {"Boğa" if kisabull else "Ayı"}
- Uzun vade: {"Boğa" if makrobull else "Ayı"}
- Pozisyon: BTC {btcpctnow}% | Altın {altpctnow}% | Bakır {bakirpctnow}%

PORTFÖY PERFORMANSI
- 8Y Rotasyon: {fmtusd(rotson)} ({fmtpct(rotkazanc * 100)})
- BTC al-tut: {fmtusd(bhbtcson)} ({fmtpct(bhbtck * 100)})
- Altın al-tut: {fmtusd(bhaltson)} ({fmtpct(bhaltk * 100)})
- Bakır al-tut: {fmtusd(bhbakirson)} ({fmtpct(bhbakirk * 100)})
- Maks. Drawdown: {fmtpct(stats['maxdd'])}

İŞLEM ÖZETİ
{tradelog.iloc[-1].to_dict()}

Soru: {soru}""")
        if yanit:
            st.markdown(f'<div class="lk-ai-box">{yanit}</div>', unsafe_allow_html=True)
elif soru and not GEMINIKEY:
    st.info("GEMINIAPIKEY olmadan soru yanıtlanamaz.")

st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
if st.button("Güncel Durumu Telegrama Gönder"):
    if not TOKEN:
        st.error("TELEGRAMTOKEN eksik.")
    elif not CHATID:
        st.error("TELEGRAMCHATID eksik.")
    else:
        rapor = f"""LIKİDİTE KOMPOZİT PANEL
BTC {fmtusd(btcfiyat)} | {fmtpct(btcdegisim)}
Altın {fmtusd(altfiyat)} | {fmtpct(altdegisim)}
Bakır {fmtusd(bakirfiyat)} | {fmtpct(bakirdegisim)}
Rejim {rejimetiketi}
Kısa Vade {"Boğa" if kisabull else "Ayı"}
Uzun Vade {"Boğa" if makrobull else "Ayı"}
Pozisyon BTC {btcpctnow}% | Altın {altpctnow}% | Bakır {bakirpctnow}%
8Y Rotasyon {fmtusd(rotson)} | {fmtpct(rotkazanc * 100)}
BTC Al-Tut {fmtusd(bhbtcson)} | {fmtpct(bhbtck * 100)}
Altın Al-Tut {fmtusd(bhaltson)} | {fmtpct(bhaltk * 100)}
Bakır Al-Tut {fmtusd(bhbakirson)} | {fmtpct(bhbakirk * 100)}
{datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": CHATID, "text": rapor, "parse_mode": "Markdown"},
                timeout=10,
            )
            if r.ok:
                st.success("Telegrama gönderildi.")
                state = loadstate()
                state["sontelegram"] = datetime.now().strftime("%d.%m.%Y %H:%M")
                savestate(state)
            else:
                st.error(f"Telegram hatası: {r.text}")
        except Exception as e:
            st.error(f"Bağlantı hatası: {e}")
