import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# ── SAYFA AYARI ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="LMI Likidite Paneli", layout="wide", page_icon="◆")

# ── CSS TEMA (LIGHT) ──────────────────────────────────────────────────────────
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&family=JetBrains+Mono:wght=400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; color: {TEXT}; }}
.lk-header {{ padding: 26px 4px 18px 4px; border-bottom: 1px solid {BORDER}; margin-bottom: 22px; }}
.lk-eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #3B82F6; margin-bottom: 6px; }}
.lk-title {{ font-size: 30px; font-weight: 700; color: {TEXT2}; margin: 0; letter-spacing: -0.01em; }}
.lk-subtitle {{ font-size: 14px; color: {SUB}; margin-top: 5px; }}
div[data-testid="stMetric"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 14px 16px; }}
div[data-testid="stMetric"] label {{ color: {SUB} !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.04em; }}
div[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-size: 20px !important; color: {TEXT2} !important; }}
.lk-regime {{ border-radius: 12px; padding: 13px 18px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; line-height: 1.6; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.lk-regime-strong-on  {{ background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.5);  color: #22C55E; }}
.lk-regime-weak-on    {{ background: rgba(59,130,246,0.10);  border-color: rgba(59,130,246,0.4);  color: #3B82F6; }}
.lk-regime-weak-off   {{ background: rgba(249,115,22,0.10); border-color: rgba(249,115,22,0.4); color: #F97316; }}
.lk-regime-strong-off {{ background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.4);  color: #EF4444; }}
.lk-section {{ font-size: 15px; font-weight: 600; color: {TEXT2}; margin: 28px 0 12px 0; padding-left: 10px; border-left: 3px solid #3B82F6; }}
</style>
""", unsafe_allow_html=True)

# ── BAŞLIK ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">BTC · XAU · XAG · XCU · DXY · Likidite Momentum Endeksi (LMI)</div>
    <p class="lk-title">Yalın Likidite Momentum Paneli</p>
    <p class="lk-subtitle">5'li makro finansal gösterge seti üzerinden gelişmiş risk iştahı ve güvenli liman rotasyonu</p>
</div>
""", unsafe_allow_html=True)

# ── REJİM TESPİT FONKSİYONU ───────────────────────────────────────────────────
def rejim_tespit(lmi, s20, s100):
    """
    LMI formülüne göre yön tayini yapar. LMI yükseldikçe risk iştahı artar.
    """
    if lmi > s20 and lmi > s100:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢🟢 GÜÇLÜ BOĞA", "Küresel likidite zirvede · Risk iştahı maksimum")
    elif lmi > s100 and lmi < s20:
        return ("Defansif Boğa", 50, 50, "weak-on", "🔵🟢 DEFANSİF BOĞA", "Ana makro trend yukarı · Kısa vadeli düzeltme")
    elif lmi < s100 and lmi > s20:
        return ("Erken Uyarı", 0, 100, "weak-off", "🟠🔴 ERKEN UYARI", "Ana trend aşağı döndü · Kısa vadeli geçici tepki")
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴🔴 GÜÇLÜ AYI", "Likidite krizi ve güçlü dolar · Tam koruma modu")

# ── FORMATLAMA YARDIMCILARI ───────────────────────────────────────────────────
def fmt_pct(x): return f"%{x:+.1f}"
def fmt_usd(x): return f"${x:,.0f}"

# ── VERİ GETİRME ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def verileri_getir():
    symbols = {
        "GC=F": "Altin", 
        "HG=F": "Bakir", 
        "BTC-USD": "Bitcoin", 
        "SI=F": "Gumus", 
        "DX-Y.NYB": "DXY"
    }
    df = yf.download(list(symbols.keys()), period="8y", interval="1d",
                     auto_adjust=False, multi_level_index=False, progress=False)
    if df.empty:
        return pd.DataFrame()
    if "Close" in df.columns:
        df = df["Close"]
    df = df.rename(columns={k: v for k, v in symbols.items() if k in df.columns})
    cols = ["Altin", "Bakir", "Bitcoin", "Gumus", "DXY"]
    return df[cols].ffill().bfill()

# ── BACKTEST SİSTEMİ ──────────────────────────────────────────────────────────
def backtest_rotasyon(df):
    d = df.copy()
    
    # Yeni LMI Formülü: ((BTC / Altın) * (Bakır / Gümüş)) / DXY
    d["LMI"] = ((d["Bitcoin"] / d["Altin"]) * (d["Bakir"] / d["Gumus"])) / d["DXY"]
    d["SMA20"] = d["LMI"].rolling(20).mean()
    d["SMA100"] = d["LMI"].rolling(100).mean()
    d = d.dropna().copy()

    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    trade_rows, equity, btc_pct_list, alt_pct_list = [], [], [], []
    btc_gun = alt_gun = 0
    max_port = 10000.0
    max_dd = 0.0

    for idx, row in d.iterrows():
        lmi, s20, s100 = row["LMI"], row["SMA20"], row["SMA100"]
        bp, ap = float(row["Bitcoin"]), float(row["Altin"])

        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(lmi, s20, s100)
        port_val = cash + btc_qty * bp + alt_qty * ap
        changed  = (prev_regime is None) or (isim != prev_regime)

        if changed:
            if isim == "Güçlü Boğa":
                btc_qty = port_val / bp; alt_qty = cash = 0.0
            elif isim == "Defansif Boğa":
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

    d["Portfoy"]  = equity
    d["BtcPct"]   = btc_pct_list
    d["AltinPct"] = alt_pct_list

    stats = {
        "islem_sayisi": len(trade_rows),
        "btc_gun":      btc_gun,
        "alt_gun":      alt_gun,
        "max_dd":       round(max_dd, 1),
        "toplam_gun":   len(d),
    }
    return d, pd.DataFrame(trade_rows), stats

# ── ANA UYGULAMA AKIŞI ────────────────────────────────────────────────────────
try:
    raw = verileri_getir()
    if raw.empty or len(raw) < 110:
        st.error("Veriler yüklenemedi veya yeterli veri yok.")
        st.stop()

    data, trade_log, stats = backtest_rotasyon(raw)

    last       = data.iloc[-1]
    btc_fiyat  = float(last["Bitcoin"])
    alt_fiyat  = float(last["Altin"])
    son_lmi    = float(last["LMI"])
    s20        = float(last["SMA20"])
    s100       = float(last["SMA100"])

    isim_now, btc_pct_now, alt_pct_now, rejim_kodu, rejim_etiketi, rejim_aciklama = \
        rejim_tespit(son_lmi, s20, s100)

    # Karşılaştırma Portföyleri
    data["BH_BTC"]   = (10000.0 / float(data["Bitcoin"].iloc[0])) * data["Bitcoin"]
    data["BH_Altin"] = (10000.0 / float(data["Altin"].iloc[0]))   * data["Altin"]

    rot_son    = float(data["Portfoy"].iloc[-1])
    rot_kazanc = (rot_son    / 10000.0 - 1) * 100
    bh_btc_son = float(data["BH_BTC"].iloc[-1])
    bh_btc_k   = (bh_btc_son / 10000.0 - 1) * 100
    bh_alt_son = float(data["BH_Altin"].iloc[-1])
    bh_alt_k   = (bh_alt_son / 10000.0 - 1) * 100

    btc_degisim = (btc_fiyat / float(data["Bitcoin"].iloc[-2]) - 1) * 100
    alt_degisim = (alt_fiyat / float(data["Altin"].iloc[-2]) - 1) * 100

    # ── 1. METRİK KARTLARI ────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin Fiyatı", fmt_usd(btc_fiyat), fmt_pct(btc_degisim) + " bugün")
    c2.metric("Altın Ons",      fmt_usd(alt_fiyat), fmt_pct(alt_degisim) + " bugün")
    c3.metric("LMI Rotasyon (Yeni)", fmt_usd(rot_son), fmt_pct(rot_kazanc))
    c4.metric("BTC Al-Tut",     fmt_usd(bh_btc_son), fmt_pct(bh_btc_k))
    c5.metric("Altın Al-Tut",   fmt_usd(bh_alt_son), fmt_pct(bh_alt_k))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 2. REJİM BANNER ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="lk-regime lk-regime-{rejim_kodu}">
        <span>{rejim_etiketi}</span>
        <span style="font-weight:400; font-size:12px; color:#7C8595">{rejim_aciklama}</span>
        <span style="margin-left:auto; font-size:13px;">
            Mevcut Dağılım: <b style="color:#22C55E">BTC %{btc_pct_now}</b>
            &nbsp;·&nbsp;
            <b style="color:#F97316">Altın %{alt_pct_now}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    # ── 3. STRATEJİ İSTATİSTİKLERİ ────────────────────────────────────────────
    st.markdown('<div class="lk-section">LMI Model Performans İstatistikleri</div>', unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Toplam Sinyal Değişimi", str(stats["islem_sayisi"]), "Geçiş")
    s2.metric("Bitcoin'de Kalınan Süre", f"{stats['btc_gun']} Gün", fmt_pct(stats['btc_gun'] / stats['toplam_gun'] * 100))
    s3.metric("Altın'da Kalınan Süre", f"{stats['alt_gun']} Gün", fmt_pct(stats['alt_gun'] / stats['toplam_gun'] * 100))
    s4.metric("Maksimum Drawdown (Değer Kaybı)", fmt_pct(stats["max_dd"]))

    # ── 4. LMI ENDEKS VE TREND GRAFİĞİ ────────────────────────────────────────
    st.markdown('<div class="lk-section">Likidite Momentum Endeksi (LMI) & Hareketli Ortalamalar</div>', unsafe_allow_html=True)
    
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=data.index, y=data["LMI"], name="LMI Endeks", line=dict(color="#6B7280", width=1.2)))
    fig1.add_trace(go.Scatter(x=data.index, y=data["SMA20"], name="SMA20 (Kısa Trend)", line=dict(color="#3B82F6", width=1.5, dash="dot")))
    fig1.add_trace(go.Scatter(x=data.index, y=data["SMA100"], name="SMA100 (Ana Trend)", line=dict(color="#22C55E", width=2.2)))
    
    fig1.update_layout(
        height=400, template=PLOTTEM, paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT), margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
        legend=dict(orientation="h", y=1.06, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig1, use_container_width=True)

    # ── 5. PORTFÖY BÜYÜME GRAFİĞİ ─────────────────────────────────────────────
    st.markdown('<div class="lk-section">Kümülatif Portföy Getirileri (10.000$ Başlangıç)</div>', unsafe_allow_html=True)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=data.index, y=data["Portfoy"], name="LMI Rotasyon Stratejisi", line=dict(color="#22C55E", width=2.5)))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_BTC"], name="Sadece BTC Al-Tut", line=dict(color="#F59E0B", width=1.5, dash="dash")))
    fig2.add_trace(go.Scatter(x=data.index, y=data["BH_Altin"], name="Sadece Altın Al-Tut", line=dict(color="#9CA3AF", width=1.5, dash="dot")))
    
    fig2.update_layout(
        height=380, template=PLOTTEM, paper_bgcolor=PLOTBG, plot_bgcolor=PLOTBG,
        font=dict(family="Inter", color=TEXT), margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
        legend=dict(orientation="h", y=1.06, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig2, use_container_width=True)

    # ── 6. SADELEŞTİRİLMİŞ İŞLEM GÜNLÜĞÜ ──────────────────────────────────────
    st.markdown('<div class="lk-section">Tarihsel Rejim Geçişleri (Son 15 Geçiş)</div>', unsafe_allow_html=True)
    st.dataframe(trade_log.tail(15).iloc[::-1], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Sistem çalışırken bir hata oluştu: {e}")
