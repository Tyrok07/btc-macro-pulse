import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime, timedelta

# ==============================================================================
# 1. GLOBAL PANORAMA VE PRODÜKSİYON AYARLARI
# ==============================================================================
st.set_page_config(
    page_title="Süper Kompozit LMI Likidite Paneli v2 Pro",
    layout="wide",
    page_icon="◆",
    initial_sidebar_state="expanded"
)

# [Kritik Entegrasyon Noktaları]
TELEGRAM_TOKEN   = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
GEMINI_API_KEY   = "YOUR_GEMINI_API_KEY"

# ==============================================================================
# 2. GELİŞMİŞ PREMIUM CSS VE LIGHT THEME ARAYÜZ MİMARİSİ
# ==============================================================================
BG      = "#F4F6FA"
CARD    = "#FFFFFF"
BORDER  = "#E2E6EF"
BORDER2 = "#CBD2E0"
TEXT    = "#1A1D23"
TEXT2   = "#111318"
SUB     = "#6B7280"
MUTEDTX = "#374151"
PLOTBG  = "#FFFFFF"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&family=JetBrains+Mono:wght=400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; color: {TEXT}; }}

/* Header Alanı */
.lk-header {{ padding: 24px 4px 16px 4px; border-bottom: 1px solid {BORDER}; margin-bottom: 25px; }}
.lk-eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; color: #3B82F6; margin-bottom: 6px; }}
.lk-title {{ font-size: 32px; font-weight: 700; color: {TEXT2}; margin: 0; letter-spacing: -0.02em; }}
.lk-subtitle {{ font-size: 14px; color: {SUB}; margin-top: 6px; }}

/* Metrik Kartları Geliştirmeleri */
div[data-testid="stMetric"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; padding: 18px 22px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
div[data-testid="stMetric"] label {{ color: {SUB} !important; font-size: 11px !important; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }}
div[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-size: 24px !important; font-weight: 700; color: {TEXT2} !important; }}

/* Rejim Banner Kartları */
.lk-regime {{ border-radius: 14px; padding: 18px 24px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 14.5px; line-height: 1.6; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 25px; }}
.lk-regime-strong-on  {{ background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.4);  color: #16A34A; }}
.lk-regime-weak-on    {{ background: rgba(59,130,246,0.12);  border-color: rgba(59,130,246,0.4);  color: #2563EB; }}
.lk-regime-weak-off   {{ background: rgba(249,115,22,0.12); border-color: rgba(249,115,22,0.4); color: #EA580C; }}
.lk-regime-strong-off {{ background: rgba(239,68,68,0.12);  border-color: rgba(239,68,68,0.4);  color: #DC2626; }}

/* Bölüm Başlıkları */
.lk-section {{ font-size: 17px; font-weight: 700; color: {TEXT2}; margin: 36px 0 16px 0; padding-left: 12px; border-left: 4px solid #3B82F6; letter-spacing: -0.01em; }}

/* AI Bilgi Kutusu */
.ai-box {{ background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 14px; padding: 24px; margin-top: 15px; box-shadow: 0 1px 4px rgba(0,0,0,0.01); line-height: 1.75; font-size: 14.5px; }}
.ai-badge {{ background: #EFF6FF; color: #1E40AF; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; font-family: 'JetBrains Mono', monospace; display: inline-block; margin-bottom: 12px; }}

/* Statik Tablo Hücreleri ve Genel İyileştirmeler */
.custom-table-title {{ font-size: 13px; font-weight: 600; color: {TEXT2}; margin-bottom: 8px; }}
</style>
""", unsafe_allow_html=True)

# Başlık Paneli Çıktısı
st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">KANTİTATİF MAKRO ROTASYON MOTORU & ANALİTİK PRODÜKSİYON PANELİ</div>
    <p class="lk-title">Süper Kompozit LMI Likidite Paneli v2 Pro</p>
    <p class="lk-subtitle">Bitcoin, Altın, Bakır, Gümüş ve DXY parametrelerini harmanlayan 5 boyutlu kurumsal risk iştahı algoritması</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. KÜTÜPHANESİZ DOĞRUDAN HTTP API İLETİŞİM KATMANI (NATIVE REQUESTS)
# ==============================================================================
def telegram_mesaj_gonder(metin):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": metin, "parse_mode": "Markdown"}, timeout=12)
        return r.status_code == 200
    except:
        return False

def gemini_api_ile_analiz(prompt):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return "Gemini API Anahtarı eksik veya geçersiz yapılandırılmış. Lütfen kodun tepesindeki anahtarı güncelleyin."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=18)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['candidates'][0]['content']['parts'][0]['text']
        return f"Gemini Sunucu Hatası (Durum Kodu: {response.status_code}): {response.text}"
    except Exception as e:
        return f"Yapay zeka motoruna asenkron bağlantı sağlanırken bir hata oluştu: {e}"

# ==============================================================================
# 4. KANTİTATİF REJİM MATRİSİ VE SINIFLANDIRICI
# ==============================================================================
def rejim_tespit(lmi, s20, s100):
    """
    Süper Kompozit Likidite Momentum Endeksi (LMI) kırılımlarına göre rejim tayini.
    """
    if lmi > s20 and lmi > s100:
        return ("Güçlü Boğa", 100, 0, "strong-on", "🟢 GÜÇLÜ BOĞA", "Küresel likidite genişlemesi zirvede · Kurumsal risk iştahı maksimum seviyede")
    elif lmi > s100 and lmi < s20:
        return ("Defansif Boğa", 50, 50, "weak-on", "🔵 DEFANSİF BOĞA", "Ana makro trend yukarı yönlü · Kısa vadeli teknik kar satışı ve konsolidasyon")
    elif lmi < s100 and lmi > s20:
        return ("Erken Uyarı", 0, 100, "weak-off", "🟠 ERKEN UYARI (AYI BAŞLANGICI)", "Ana makro trend aşağı döndü · Kısa vadeli geçici tepki ve dağıtım safhası")
    else:
        return ("Güçlü Ayı", 0, 100, "strong-off", "🔴 GÜÇLÜ AYI", "Sistemik likidite krizi ve agresif DXY baskısı · Tam güvenli liman koruması")

# ==============================================================================
# 5. KORUMALI VERİ ENJEKSİYONU VE İNDİKATÖR TAMPONU
# ==============================================================================
@st.cache_data(ttl=3600)
def finansal_veri_havuzunu_doldur():
    symbols = {
        "GC=F": "Altin", 
        "HG=F": "Bakir", 
        "BTC-USD": "Bitcoin", 
        "SI=F": "Gumus", 
        "DX-Y.NYB": "DXY"
    }
    # 8 Yıllık derin tarihsel veri seti
    df = yf.download(list(symbols.keys()), period="8y", interval="1d", auto_adjust=False, multi_level_index=False, progress=False)
    if df.empty or "Close" not in df.columns:
        raise ValueError("Yfinance sunucularından geçerli fiyat datası alınamadı.")
    
    df = df["Close"].rename(columns=symbols)
    # Eksik dataların temizlenmesi
    df = df[["Altin", "Bakir", "Bitcoin", "Gumus", "DXY"]].ffill().bfill()
    return df

# ==============================================================================
# 6. ENTEGRE BACKTEST SİMÜLASYONU VE DERİN ANALİTİK MOTORU
# ==============================================================================
try:
    df_raw = finansal_veri_havuzunu_doldur()
    d = df_raw.copy()
    
    # 5'li Gelişmiş Makro LMI Formülasyonu
    d["LMI"] = ((d["Bitcoin"] / d["Altin"]) * (d["Bakir"] / d["Gumus"])) / d["DXY"]
    d["SMA20"] = d["LMI"].rolling(20).mean()
    d["SMA100"] = d["LMI"].rolling(100).mean()
    d = d.dropna().copy()

    # Backtest Değişkenleri Yapılandırması
    cash = 10000.0
    btc_qty = alt_qty = 0.0
    prev_regime = None
    
    trade_rows = []
    equity_curve = []
    btc_pct_track = []
    alt_pct_track = []
    
    max_portfolio_value = 10000.0
    max_drawdown = 0.0
    btc_gun_sayisi = alt_gun_sayisi = combo_gun_sayisi = 0

    # Kronolojik Simülasyon Döngüsü
    for idx, row in d.iterrows():
        lmi, s20, s100 = row["LMI"], row["SMA20"], row["SMA100"]
        bp, ap = float(row["Bitcoin"]), float(row["Altin"])
        isim, t_btc, t_alt, _, etiket, _ = rejim_tespit(lmi, s20, s100)
        
        current_val = cash + (btc_qty * bp) + (alt_qty * ap)
        
        # Re-balance Sinyal Kontrolü
        if prev_regime is None or isim != prev_regime:
            if isim == "Güçlü Boğa":
                btc_qty = current_val / bp
                alt_qty = cash = 0.0
            elif isim == "Defansif Boğa":
                btc_qty = (current_val * 0.5) / bp
                alt_qty = (current_val * 0.5) / ap
                cash = 0.0
            else: # Erken Uyarı veya Güçlü Ayı (%100 Altın Defans Modu)
                alt_qty = current_val / ap
                btc_qty = cash = 0.0
                
            post_val = cash + (btc_qty * bp) + (alt_qty * ap)
            trade_rows.append({
                "Tarih": pd.to_datetime(idx).strftime("%Y-%m-%d"),
                "Eski ➔ Yeni Rejim": f"{prev_regime or 'BAŞLANGIÇ'} ➔ {isim}",
                "Algoritmik Etiket": etiket,
                "Hedef Dağılım": f"BTC %{t_btc} / XAU %{t_alt}",
                "Net Portföy ($)": round(post_val, 2),
                "Kümülatif Getiri (%)": round((post_val / 10000.0 - 1) * 100, 2)
            })
            prev_regime = isim

        # Günlük Hesaplama ve Risk Takipleri
        updated_val = cash + (btc_qty * bp) + (alt_qty * ap)
        max_portfolio_value = max(max_portfolio_value, updated_val)
        current_dd = (updated_val - max_portfolio_value) / max_portfolio_value * 100
        max_drawdown = min(max_drawdown, current_dd)
        
        if t_btc == 100: btc_gun_sayisi += 1
        elif t_alt == 100: alt_gun_sayisi += 1
        else: combo_gun_sayisi += 1
        
        equity_curve.append(updated_val)
        btc_pct_track.append(t_btc)
        alt_pct_track.append(t_alt)

    # İndikatör Sütun Entegrasyonları
    d["Portfoy"] = equity_curve
    d["BtcPct"] = btc_pct_track
    d["AltinPct"] = alt_pct_track
    
    # Karşılaştırma Endeksleri
    d["BH_BTC"]   = (10000.0 / d["Bitcoin"].iloc[0]) * d["Bitcoin"]
    d["BH_Altin"] = (10000.0 / d["Altin"].iloc[0]) * d["Altin"]

    # Derin İstatistiksel Hesaplamalar
    toplam_bar_sayisi = len(d)
    cagr = ((d["Portfoy"].iloc[-1] / 10000.0) ** (252 / toplam_bar_sayisi) - 1) * 100 if toplam_bar_sayisi > 0 else 0.0
    
    # ==============================================================================
    # 7. KULLANICI ARAYÜZÜ, METRİK KARTLARI VE KONTROL PANELİ
    # ==============================================================================
    last_row = d.iloc[-1]
    prev_row = d.iloc[-2]
    
    btc_f, alt_f = float(last_row["Bitcoin"]), float(last_row["Altin"])
    bak_f, gum_f, dxy_f = float(last_row["Bakir"]), float(last_row["Gumus"]), float(last_row["DXY"])
    lmi_f, s20_f, s100_f = float(last_row["LMI"]), float(last_row["SMA20"]), float(last_row["SMA100"])
    
    isim_now, btc_p_now, alt_p_now, r_kodu, r_etiket, r_aciklama = rejim_tespit(lmi_f, s20_f, s100_f)
    
    # Günlük Yüzdesel Değişim Hesaplamaları
    btc_diff = ((btc_f / float(prev_row["Bitcoin"])) - 1) * 100
    alt_diff = ((alt_f / float(prev_row["Altin"])) - 1) * 100
    strat_perf = ((d["Portfoy"].iloc[-1] / 10000.0) - 1) * 100
    
    # 5'li Ana Metrik Kartı Tasarımı
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Bitcoin (BTCUSD)", f"${btc_f:,.2f}", f"{btc_diff:+.2f}%")
    m2.metric("Altın Ons (XAUUSD)", f"${alt_f:,.2f}", f"{alt_diff:+.2f}%")
    m3.metric("LMI Stratejisi Kapanış", f"${d['Portfoy'].iloc[-1]:,.2f}", f"{strat_perf:+.1f}%")
    m4.metric("Sadece BTC (Al-Tut)", f"${d['BH_BTC'].iloc[-1]:,.2f}")
    m5.metric("Sadece Altın (Al-Tut)", f"${d['BH_Altin'].iloc[-1]:,.2f}")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Dinamik Algoritmik Rejim Paneli
    st.markdown(f"""
    <div class="lk-regime lk-regime-{r_kodu}">
        <span>{r_etiket} REJİMİ AKTİF</span>
        <span style="font-weight:400; font-size:12.5px; color:#6B7280">{r_aciklama}</span>
        <span style="margin-left:auto; font-size:13.5px;">Optimal Dağılım Modeli: <b style="color:#16A34A">BTC %{btc_p_now}</b> / <b style="color:#EA580C">Altın %{alt_p_now}</b></span>
    </div>""", unsafe_allow_html=True)

    # ==============================================================================
    # 8. GELİŞMİŞ YAPAY ZEKA VE ASENKRON ETKİLEŞİM İSTASYONU
    # ==============================================================================
    st.markdown('<div class="lk-section">🧠 Gemini AI Profesyonel Makro Analiz İstasyonu</div>', unsafe_allow_html=True)
    
    col_ai_1, col_ai_2 = st.columns([3, 2])
    
    with col_ai_1:
        st.markdown("<p class='custom-table-title'>Stratejik Model Özeti İstemi</p>", unsafe_allow_html=True)
        prompt_text = (
            f"Sen küresel bir hedge fonunun baş kantitatif stratejistisin. Güncel Makro Verilerimiz: "
            f"Bitcoin: {btc_f} USD, Altın Ons: {alt_f} USD, Bakır: {bak_f}, Gümüş: {gum_f}, DXY Endeksi: {dxy_f}. "
            f"Geliştirdiğimiz 5 boyutlu LMI modelinin son çıktısı: '{r_etiket}'. "
            f"Sistem şu an portföyü BTC %{btc_p_now} - Altın %{alt_p_now} olarak dengeliyor. "
            f"Bize bu likidite rejiminin makro arka planını anlatan, risk iştahını yorumlayan ve yatırımcıya yol gösteren 4 cümlelik kurumsal bir rapor yaz."
        )
        
        if st.button("Yapay Zeka Makro Analizini Tetikle / Güncelle"):
            with st.spinner("Gemini Kurumsal API hattına bağlanılıyor..."):
                ai_res = gemini_api_ile_analiz(prompt_text)
                st.markdown(f'<div class="ai-box"><div class="ai-badge">KANTİTATİF ANALİST RAPORU</div><br>{ai_res}</div>', unsafe_allow_html=True)
                
    with col_ai_2:
        st.markdown("<p class='custom-table-title'>Manuel Sinyal ve Entegrasyon Kontrolleri</p>", unsafe_allow_html=True)
        st.write("Aşağıdaki butonları kullanarak sistemi harici kanallara manuel olarak senkronize edebilir veya güncel datayı pushlayabilirsiniz.")
        
        if st.button("📲 Güncel Sinyali ve Matrisi Telegram Kanalına Rapor Et"):
            msg = (
                f"◆ *LMI MAKRO SİNYAL RAPORU*\n"
                f"───────────────────\n"
                f"● *Aktif Rejim:* {r_etiket}\n"
                f"● *Güncel BTC:* ${btc_f:,.2f}\n"
                f"● *Güncel Altın:* ${alt_f:,.2f}\n"
                f"● *DXY Endeksi:* {dxy_f:.2f}\n"
                f"● *Strateji Değeri:* ${d['Portfoy'].iloc[-1]:,.2f}\n"
                f"───────────────────\n"
                f"⏱ _{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}_"
            )
            if telegram_mesaj_gonder(msg):
                st.success("Telegram sinyali ve makro matris başarıyla iletildi!")
            else:
                st.error("Telegram entegrasyonu başarısız. Lütfen Token ve Chat ID parametrelerini kontrol edin.")

    # ==============================================================================
    # 9. DETAYLI STRATEJİ PERFORMANS VE ALOKASYON İSTATİSTİKLERİ
    # ==============================================================================
    st.markdown('<div class="lk-section">LMI Model Performans İstatistikleri (Detaylı Matris)</div>', unsafe_allow_html=True)
    
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Toplam Sinyal Değişimi", f"{len(trade_rows)} Sinyal", "Geçiş")
    s2.metric("Bitcoin'de Kalınan Süre", f"{btc_gun_sayisi} Gün", f"%{btc_gun_sayisi/toplam_bar_sayisi*100:.1f}")
    s3.metric("Altın'da Kalınan Süre", f"{alt_gun_sayisi} Gün", f"%{alt_gun_sayisi/toplam_bar_sayisi*100:.1f}")
    s4.metric("Yıllık Bileşik Getiri (CAGR)", f"%{cagr:.2f}", "8 Yıllık Ortalama")
    s5.metric("Maksimum Tarihsel Erime", f"%{max_drawdown:.2f}", "Drawdown Limiti")

    # ==============================================================================
    # 10. GELİŞMİŞ RENKLİ REJİM BOYAMALI (VSPAN) DETAYLI PLOTLY GRAFİKLERİ
    # ==============================================================================
    st.markdown('<div class="lk-section">Kümülâtif Performans Grafikleri & İndikatör Bölge Analizi</div>', unsafe_allow_html=True)
    
    # 2 Katmanlı Akıllı Grafik Mimarisinin İnşası
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08, 
        subplot_titles=("Portföy Özkaynak Büyüme Eğrileri (Logaritmik Ölçek)", "LMI Momentum Endeksi & Sinyal Eşikleri")
    )
    
    # Katman 1: Portföy Büyüme Çizgileri
    fig.add_trace(go.Scatter(x=d.index, y=d["Portfoy"], name="LMI Rotasyon Stratejisi v2", line=dict(color="#22C55E", width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["BH_BTC"], name="Sadece BTC Al-Tut", line=dict(color="#F59E0B", width=1.2, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["BH_Altin"], name="Sadece Altın Al-Tut", line=dict(color="#9CA3AF", width=1.2, dash="dot")), row=1, col=1)
    
    # Katman 2: LMI ve Hareketli Ortalamalar
    fig.add_trace(go.Scatter(x=d.index, y=d["LMI"], name="LMI Endeks Skoru", line=dict(color="#4B5563", width=1.0)), row=2, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["SMA20"], name="SMA20 (Kısa Vadeli İvme)", line=dict(color="#3B82F6", width=1.3, dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["SMA100"], name="SMA100 (Makro Trend Filtresi)", line=dict(color="#10B981", width=2.0)), row=2, col=1)

    # Arka Plan Rejim Boyama Algoritması (VSPAN)
    df_changes = d[d["BtcPct"] != d["BtcPct"].shift()]
    change_idx = list(df_changes.index) + [d.index[-1]]
    
    for i in range(len(change_idx) - 1):
        t_start = change_idx[i]
        t_end = change_idx[i+1]
        btc_p_val = d.loc[t_start, "BtcPct"]
        
        # Sinyal koduna göre şeffaf dikey arka plan ataması
        if btc_p_val == 100:
            fill_c = "rgba(34,197,94,0.03)"   # Boğa (Yeşil)
        elif btc_p_val == 50:
            fill_c = "rgba(59,130,246,0.03)"  # Defansif Boğa (Mavi)
        else:
            fill_c = "rgba(239,68,68,0.03)"   # Koruma / Ayı (Kırmızı)
            
        fig.add_vrect(x0=t_start, x1=t_end, fillcolor=fill_c, layer="below", line_width=0, row="all")

    # Grafik Tasarım İyileştirmeleri
    fig.update_layout(
        height=700, 
        template="plotly_white", 
        paper_bgcolor=PLOTBG, 
        plot_bgcolor=PLOTBG,
        margin=dict(l=15, r=15, t=30, b=15),
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)")
    )
    st.plotly_chart(fig, use_container_width=True)

    # ==============================================================================
    # 11. TARİHSEL GEÇİŞ DEFTERİ VE KRONOLOJİK SİNYAL KAYITLARI
    # ==============================================================================
    st.markdown('<div class="lk-section">Tarihsel Rejim Geçiş Defteri (Son 15 Makro Rotasyon)</div>', unsafe_allow_html=True)
    
    # Kronolojiyi tersten göstererek en son sinyali üste getirme
    log_df = pd.DataFrame(trade_rows)
    if not log_df.empty:
        st.dataframe(log_df.tail(15).iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("Sistem başlangıcından beri henüz bir rejim değişikliği tetiklenmedi.")

except Exception as main_error:
    st.error(f"Sistem Çalışma Zamanı Entegrasyon Hatası: {main_error}")
