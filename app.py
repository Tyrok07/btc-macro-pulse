import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json

st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #0B0E14; color: #E6E9EF; }

.lk-header {
    padding: 28px 4px 20px 4px;
    border-bottom: 1px solid #1E2430;
    margin-bottom: 24px;
}
.lk-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #6FE3B5;
    margin-bottom: 6px;
}
.lk-title {
    font-size: 30px;
    font-weight: 700;
    color: #F2F4F8;
    margin: 0;
    letter-spacing: -0.01em;
}
.lk-subtitle { font-size: 14px; color: #7C8595; margin-top: 6px; }

div[data-testid="stMetric"] {
    background: #131722;
    border: 1px solid #1E2430;
    border-radius: 10px;
    padding: 16px 18px;
}
div[data-testid="stMetric"] label {
    color: #7C8595 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px !important;
    color: #F2F4F8 !important;
}

.lk-regime {
    border-radius: 10px;
    padding: 14px 16px;
    border: 1px solid;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 13px;
    line-height: 1.6;
}
.lk-regime-strong-on  { background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.5);  color: #4ADE80; }
.lk-regime-weak-on    { background: rgba(234,179,8,0.10);  border-color: rgba(234,179,8,0.4);  color: #FCD34D; }
.lk-regime-weak-off   { background: rgba(249,115,22,0.10); border-color: rgba(249,115,22,0.4); color: #FB923C; }
.lk-regime-strong-off { background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.4);  color: #F87171; }

.lk-section {
    font-size: 15px;
    font-weight: 600;
    color: #F2F4F8;
    margin: 32px 0 12px 0;
    padding-left: 10px;
    border-left: 3px solid #6FE3B5;
}

/* Yapay zeka yorum kutusu */
.lk-ai-box {
    background: #131722;
    border: 1px solid #1E2430;
    border-radius: 12px;
    padding: 24px 28px;
    margin-top: 8px;
    line-height: 1.75;
    font-size: 15px;
    color: #C8CDD8;
}
.lk-ai-box b, .lk-ai-box strong { color: #F2F4F8; }

h1, h2, h3 { color: #F2F4F8; }
hr { border-color: #1E2430; }

.stButton > button {
    background: #131722;
    border: 1px solid #2A3140;
    color: #E6E9EF;
    border-radius: 8px;
    font-weight: 500;
    padding: 8px 18px;
}
.stButton > button:hover { border-color: #6FE3B5; color: #6FE3B5; }

.stTextInput input {
    background: #131722;
    border: 1px solid #1E2430;
    color: #E6E9EF;
    border-radius: 8px;
}
.stAlert { border-radius: 10px; }
</style>

<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / XCUUSD / BTCUSD &nbsp;·&nbsp; Likidite Kompoziti &nbsp;·&nbsp; 8 Yıllık Analiz</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Altın · Bakır · Bitcoin oranı ile küresel likiditenin yönünü ve BTC fırsatlarını takip et</p>
</div>
""", unsafe_allow_html=True)

# ── SECRETS ──────────────────────────────────────────────────────────────────
GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN   = str(st.secrets.get("TELEGRAM_TOKEN",  "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID","")).strip()

def telegram_gonder(mesaj):
    if not TOKEN or not CHAT_ID:
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"},
            timeout=10
        )
        return True
    except:
        return False

# ── VERİ ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def verileri_getir():
    semboller = {"GC=F": "Altin", "HG=F": "Bakir", "BTC-USD": "Bitcoin"}
    df = yf.download(list(semboller.keys()), period="8y", interval="1d")
    if 'Close' in df.columns:
        df = df['Close']
    df.rename(columns=semboller, inplace=True)
    return df.ffill().bfill()

# ── CLAUDE OTOMATİK YORUM ────────────────────────────────────────────────────
def gemini_api(prompt):
    """Gemini 2.0 Flash — ücretsiz Google AI Studio API'si."""
    if not GEMINI_KEY:
        return None
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
        )
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, json=body, timeout=20)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Hata: {e}"

def gemini_yorum_uret(btc_fiyat, son_rasyo, sma10, sma50,
                      rejim_etiketi, kazanc, bh_kazanc,
                      strateji_deger, bh_deger):
    if not GEMINI_KEY:
        return None
    prompt = f"""
Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının anlayabileceği,
sade Türkçe ile 4-6 cümlelik bir özet yorum yaz. Teknik jargon kullanma.
Grafik, rasyo, SMA gibi terimleri açıkla. Sonunda tek cümleyle "Şu an ne yapmalı?" önerisi ver.

MEVCUT VERİLER:
- Bitcoin Fiyatı: ${btc_fiyat:,.0f}
- Likidite Rasyosu (Altın/Bakır/BTC): {son_rasyo:.4e}
- Kısa Vade Sinyal Hattı (SMA10): {sma10:.4e}
- Uzun Vade Sinyal Hattı (SMA50): {sma50:.4e}
- Mevcut Piyasa Rejimi: {rejim_etiketi}
- 8 Yıllık Strateji Kazancı: %{kazanc:+.1f} (${strateji_deger:,.0f})
- BTC Al-Tut Kazancı (kıyas): %{bh_kazanc:+.1f} (${bh_deger:,.0f})

REJİM MANTIĞI:
- Rasyo < SMA10 ve SMA50 → Güçlü Boğa (likidite kripto tarafa akıyor)
- Rasyo < SMA50 ama > SMA10 → Boğa trendi içinde kısa düzeltme
- Rasyo > SMA50 ama < SMA10 → Ayı trendi içinde kısa toparlanma
- Rasyo > SMA10 ve SMA50 → Güçlü Ayı (likidite güvenli limana kaçıyor)

Yanıtın sadece yorum metni olsun, başlık veya madde işareti ekleme.
"""
    return gemini_api(prompt)

# ── ANA UYGULAMA ──────────────────────────────────────────────────────────────
try:
    data = verileri_getir()

    if data.empty or len(data) < 60:
        st.error("Veri havuzu henüz yeterli büyüklükte değil.")
    else:
        # Rasyo: Altın / (Bakır × Bitcoin) — BTC ile ters korelasyon
        data['Rasyo'] = data['Altin'] / (data['Bakir'] * data['Bitcoin'])

        # ÇİFT SMA — makro döngü (50) + kısa vade akış (10)
        data['SMA10'] = data['Rasyo'].rolling(window=10).mean()
        data['SMA50'] = data['Rasyo'].rolling(window=50).mean()
        data = data.dropna().copy()

        son_rasyo = data['Rasyo'].iloc[-1]
        sma10     = data['SMA10'].iloc[-1]
        sma50     = data['SMA50'].iloc[-1]
        btc_fiyat = data['Bitcoin'].iloc[-1]

        # 4 Rejim Durumu
        makro_bull = son_rasyo < sma50   # uzun vade boğa
        kisa_bull  = son_rasyo < sma10   # kısa vade boğa

        if makro_bull and kisa_bull:
            rejim_kodu   = "strong_on"
            rejim_etiketi = "🟢🟢 GÜÇLÜ BOĞA"
            rejim_aciklama = "Her iki sinyal de BTC lehine · En güçlü alım bölgesi"
            status_text  = "🟢🟢 GÜÇLÜ BOĞA — Her iki sinyal BTC lehine"
        elif makro_bull and not kisa_bull:
            rejim_kodu   = "weak_on"
            rejim_etiketi = "🟡🟢 BOĞA + Kısa Düzeltme"
            rejim_aciklama = "Büyük trend yukarı · Kısa vadede hafif baskı"
            status_text  = "🟡🟢 BOĞA TRENDİ — Kısa vadeli düzeltme içinde"
        elif not makro_bull and kisa_bull:
            rejim_kodu   = "weak_off"
            rejim_etiketi = "🟠🔴 AYI + Kısa Toparlanma"
            rejim_aciklama = "Büyük trend aşağı · Kısa vadede geçici rahatlama"
            status_text  = "🟠🔴 AYI TRENDİ — Kısa vadeli toparlanma içinde"
        else:
            rejim_kodu   = "strong_off"
            rejim_etiketi = "🔴🔴 GÜÇLÜ AYI"
            rejim_aciklama = "Her iki sinyal de BTC aleyhine · En güçlü kaçış bölgesi"
            status_text  = "🔴🔴 GÜÇLÜ AYI — Her iki sinyal BTC aleyhine"

        # BTC Al-Tut kıyası
        ilk_btc = data['Bitcoin'].iloc[0]
        bh_adet = 10000.0 / ilk_btc
        data['BuyHold'] = bh_adet * data['Bitcoin']
        bh_son    = data['BuyHold'].iloc[-1]
        bh_kazanc = (bh_son - 10000.0) / 10000.0 * 100

        # 8 Yıllık Backtest (sadece güçlü sinyallerde işlem)
        # Kural: İKİSİ DE aynı yönde → işlem yap, karışık → nakitte kal
        bakiye    = 10000.0
        btc_adet_bt  = 0.0
        pozisyon  = False
        gunluk_bt = []

        for i in range(len(data)):
            r  = data['Rasyo'].iloc[i]
            s10 = data['SMA10'].iloc[i]
            s50 = data['SMA50'].iloc[i]
            fiyat = data['Bitcoin'].iloc[i]

            iki_boga = (r < s10) and (r < s50)
            iki_ayi  = (r > s10) and (r > s50)

            if iki_boga and not pozisyon:
                btc_adet_bt = bakiye / fiyat
                bakiye = 0.0
                pozisyon = True
            elif iki_ayi and pozisyon:
                bakiye = btc_adet_bt * fiyat
                btc_adet_bt = 0.0
                pozisyon = False

            deger = bakiye if not pozisyon else (btc_adet_bt * fiyat)
            gunluk_bt.append(deger)

        data['Strateji'] = gunluk_bt
        strateji_son    = data['Strateji'].iloc[-1]
        strateji_kazanc = (strateji_son - 10000.0) / 10000.0 * 100

        # ── METRIK KARTLARI ───────────────────────────────────────────────────
        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Bitcoin Fiyatı", f"${btc_fiyat:,.0f}")
        col2.metric("Kısa Vade (SMA10)",
                    "Boğa ↓" if kisa_bull else "Ayı ↑",
                    f"Rasyo {'<' if kisa_bull else '>'} SMA10")
        col3.metric("Uzun Vade (SMA50)",
                    "Boğa ↓" if makro_bull else "Ayı ↑",
                    f"Rasyo {'<' if makro_bull else '>'} SMA50")
        col4.metric("8Y Strateji Bakiyesi",
                    f"${strateji_son:,.0f}",
                    f"%{strateji_kazanc:+.1f}")
        col5.metric("BTC Al-Tut Kıyası",
                    f"${bh_son:,.0f}",
                    f"%{bh_kazanc:+.1f}")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # Rejim banner
        st.markdown(f"""
<div class="lk-regime lk-regime-{rejim_kodu.replace('_','-')}">
    {rejim_etiketi}
    <span style="font-weight:400; font-size:12px; color:#7C8595; margin-left:14px">{rejim_aciklama}</span>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        fark = strateji_son - bh_son
        if fark < 0:
            st.warning(f"Strateji al-tuta kıyasla **${abs(fark):,.0f}** geride  ·  Strateji %{strateji_kazanc:+.1f}  vs  Al-Tut %{bh_kazanc:+.1f}  ·  (Strateji karışık sinyallerde nakitte kalıyor — düşük volatilite avantajı)")
        else:
            st.success(f"Strateji al-tutun **${fark:,.0f}** önünde  ·  Strateji %{strateji_kazanc:+.1f}  vs  Al-Tut %{bh_kazanc:+.1f}")

        # ── ANA GRAFİK — Rasyo + SMA10 + SMA50 + BTC ────────────────────────
        st.markdown('<div class="lk-section">Likidite Rasyosu · SMA10 (Kısa) · SMA50 (Uzun) · BTC Fiyatı</div>', unsafe_allow_html=True)

        fig = go.Figure()

        # Rasyo
        fig.add_trace(go.Scatter(
            x=data.index, y=data['Rasyo'],
            name="Süper Rasyo",
            line=dict(color='#7C8595', width=1.0),
            opacity=0.7
        ))

        # SMA10 — renk değişen (kısa vade)
        data['Renk10'] = data.apply(
            lambda r: '#4ADE80' if r['Rasyo'] < r['SMA10'] else '#F87171', axis=1)
        for _, grp in data.groupby((data['Renk10'] != data['Renk10'].shift()).cumsum()):
            fig.add_trace(go.Scatter(
                x=grp.index, y=grp['SMA10'],
                mode='lines',
                line=dict(color=grp['Renk10'].iloc[0], width=1.5, dash='dot'),
                showlegend=False
            ))

        # SMA50 — renk değişen (uzun vade, daha kalın)
        data['Renk50'] = data.apply(
            lambda r: '#4ADE80' if r['Rasyo'] < r['SMA50'] else '#F87171', axis=1)
        for _, grp in data.groupby((data['Renk50'] != data['Renk50'].shift()).cumsum()):
            fig.add_trace(go.Scatter(
                x=grp.index, y=grp['SMA50'],
                mode='lines',
                line=dict(color=grp['Renk50'].iloc[0], width=2.5),
                showlegend=False
            ))

        # BTC (sağ eksen)
        fig.add_trace(go.Scatter(
            x=data.index, y=data['Bitcoin'],
            name="BTC Fiyatı",
            line=dict(color='#F0B90B', width=1.3, dash='dot'),
            yaxis="y2"
        ))

        # Görünmez legend trace'ler
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
            line=dict(color='#4ADE80', width=2.5), name="SMA50 Boğa"))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
            line=dict(color='#F87171', width=2.5), name="SMA50 Ayı"))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
            line=dict(color='#4ADE80', width=1.5, dash='dot'), name="SMA10 Boğa"))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
            line=dict(color='#F87171', width=1.5, dash='dot'), name="SMA10 Ayı"))

        fig.update_layout(
            height=580,
            template="plotly_dark",
            paper_bgcolor='#0B0E14', plot_bgcolor='#0B0E14',
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor='#1E2430', linecolor='#1E2430'),
            yaxis=dict(title="Süper Rasyo", gridcolor='#1E2430',
                       title_font=dict(color="#7C8595"), tickfont=dict(color="#7C8595")),
            yaxis2=dict(title="BTC (USD)", overlaying="y", side="right",
                        title_font=dict(color="#F0B90B"), tickfont=dict(color="#F0B90B"),
                        gridcolor='rgba(0,0,0,0)'),
            legend=dict(orientation="h", y=1.04, x=1, xanchor="right",
                        bgcolor='rgba(0,0,0,0)', font=dict(size=11))
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── PORTFÖY KARŞILAŞTIRMA GRAFİĞİ ────────────────────────────────────
        st.markdown('<div class="lk-section">Strateji vs BTC Al-Tut · Giriş $10.000</div>', unsafe_allow_html=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=data.index, y=data['Strateji'],
            name="Çift SMA Stratejisi",
            line=dict(color='#6FE3B5', width=2)
        ))
        fig2.add_trace(go.Scatter(
            x=data.index, y=data['BuyHold'],
            name="BTC Al-Tut",
            line=dict(color='#F0B90B', width=2)
        ))
        fig2.update_layout(
            height=380,
            template="plotly_dark",
            paper_bgcolor='#0B0E14', plot_bgcolor='#0B0E14',
            font=dict(family="Inter, sans-serif", color="#E6E9EF"),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor='#1E2430'),
            yaxis=dict(title="Portföy Değeri (USD)", gridcolor='#1E2430',
                       title_font=dict(color="#7C8595"), tickfont=dict(color="#7C8595")),
            legend=dict(orientation="h", y=1.04, x=1, xanchor="right",
                        bgcolor='rgba(0,0,0,0)')
        )
        st.plotly_chart(fig2, use_container_width=True)

        # ── CLAUDE OTOMATİK YORUM KUTUSU ─────────────────────────────────────
        st.markdown('<div class="lk-section">Yapay Zeka Piyasa Yorumu</div>', unsafe_allow_html=True)

        if GEMINI_KEY:
            with st.spinner("Piyasa verileri yorumlanıyor..."):
                yorum = gemini_yorum_uret(
                    btc_fiyat, son_rasyo, sma10, sma50,
                    rejim_etiketi, strateji_kazanc, bh_kazanc,
                    strateji_son, bh_son
                )
            if yorum:
                st.markdown(f'<div class="lk-ai-box">{yorum}</div>', unsafe_allow_html=True)
        else:
            st.info("Otomatik yorum için Streamlit secrets'a `GEMINI_API_KEY` ekleyin. (Ücretsiz: aistudio.google.com)")

        # Soru-cevap kutusu
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        user_soru = st.text_input(
            "Soru sor",
            label_visibility="collapsed",
            placeholder="Aklınıza takılan bir şey mi var? Buraya yazın..."
        )
        if user_soru and GEMINI_KEY:
            with st.spinner("Yanıt hazırlanıyor..."):
                baglam = f"""
Sen bir piyasa analisti danışmanısın. Şu anki durum:
- BTC: ${btc_fiyat:,.0f}
- Rejim: {rejim_etiketi}
- Kısa vade (SMA10): {'Boğa' if kisa_bull else 'Ayı'}
- Uzun vade (SMA50): {'Boğa' if makro_bull else 'Ayı'}
- 8Y Strateji: %{strateji_kazanc:+.1f}  |  Al-Tut: %{bh_kazanc:+.1f}

Sıradan bir yatırımcıya sade Türkçe ile, kısa ve net yanıt ver. Teknik terimler kullanma.
Kullanıcı sorusu: {user_soru}
"""
                yanit = gemini_api(baglam)
                if yanit:
                    st.markdown(f'<div class="lk-ai-box">{yanit}</div>', unsafe_allow_html=True)

        # ── TELEGRAM ─────────────────────────────────────────────────────────
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("Güncel Durumu Telegram'a Gönder"):
            rapor = (
                f"◆ *LİKİDİTE KOMPOZİT PANELİ* ◆\n\n"
                f"🪙 BTC: ${btc_fiyat:,.0f}\n"
                f"📊 Rejim: {status_text}\n"
                f"  • Kısa Vade: {'🟢 Boğa' if kisa_bull else '🔴 Ayı'}\n"
                f"  • Uzun Vade: {'🟢 Boğa' if makro_bull else '🔴 Ayı'}\n\n"
                f"💼 8Y Strateji: ${strateji_son:,.0f} (%{strateji_kazanc:+.1f})\n"
                f"📈 Al-Tut: ${bh_son:,.0f} (%{bh_kazanc:+.1f})"
            )
            if telegram_gonder(rapor):
                st.success("Telegram'a gönderildi.")
            else:
                st.warning("Telegram bilgileri eksik veya hatalı.")

except Exception as e:
    st.error(f"Genel hata: {e}")
