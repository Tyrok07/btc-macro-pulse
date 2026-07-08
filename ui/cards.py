from __future__ import annotations

import streamlit as st

from utils.formatters import fmt_pct, fmt_usd


def render_top_metrics(last, stats: dict) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bitcoin", fmt_usd(float(last["Bitcoin"])), fmt_pct(stats["btc_degisim"]) + " son gün")
    c2.metric("Altın", fmt_usd(float(last["Altin"])), fmt_pct(stats["alt_degisim"]) + " son gün")
    c3.metric("8Y Rotasyon", fmt_usd(stats["rot_son"]), fmt_pct(stats["rot_kazanc"]))
    c4.metric("BTC Al-Tut", fmt_usd(stats["bh_btc_son"]), fmt_pct(stats["bh_btc_k"]))
    c5.metric("Altın Al-Tut", fmt_usd(stats["bh_alt_son"]), fmt_pct(stats["bh_alt_k"]))
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)


def render_regime_banner(last) -> None:
    st.markdown(f"""
<div class="lk-regime lk-regime-{last['RegimeCode']}">
    <span>{last['RegimeLabel']}</span>
    <span style="font-weight:400; font-size:12px; color:#7C8595">{last['RegimeDescription']}</span>
    <span style="margin-left:auto; font-size:13px;">
        Şu an: <b style="color:#F0B90B">BTC %{int(last['BtcPct'])}</b>
        &nbsp;·&nbsp;
        <b style="color:#E5C07B">Altın %{int(last['AltinPct'])}</b>
    </span>
</div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


def render_benchmark_message(stats: dict) -> None:
    fark = stats["rotation_advantage"]
    if fark >= 0:
        st.success(f"Rotasyon BTC al-tutun **{fmt_usd(fark)}** önünde  ·  "
                   f"Rotasyon {fmt_pct(stats['rot_kazanc'])}  vs  "
                   f"BTC al-tut {fmt_pct(stats['bh_btc_k'])}  vs  "
                   f"Altın al-tut {fmt_pct(stats['bh_alt_k'])}")
    else:
        st.warning(f"Rotasyon BTC al-tutun **{fmt_usd(abs(fark))}** gerisinde  ·  "
                   f"Rotasyon {fmt_pct(stats['rot_kazanc'])}  vs  "
                   f"BTC al-tut {fmt_pct(stats['bh_btc_k'])}  vs  "
                   f"Altın al-tut {fmt_pct(stats['bh_alt_k'])}")


def render_performance_metrics(stats: dict) -> None:
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Toplam İşlem", str(stats["islem_sayisi"]), "rejim geçişi")
    s2.metric("BTC'de Geçen Süre", f"{stats['btc_gun']} gün", fmt_pct(stats["btc_gun_pct"]))
    s3.metric("Altın'da Geçen Süre", f"{stats['alt_gun']} gün", fmt_pct(stats["alt_gun_pct"]))
    s4.metric("Maks. Drawdown", fmt_pct(stats["max_dd"]))
    s5.metric("Rotasyon Avantajı", fmt_usd(stats["rotation_advantage"]))


def render_alarm_status(state: dict, kontrol_aralik: int, scheduler_ok: bool) -> None:
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Kontrol Sıklığı", f"Her {kontrol_aralik} dakika", "✅ Aktif" if scheduler_ok else "⚠️ APScheduler eksik")
    a2.metric("Son Kontrol", state.get("son_kontrol", "Bekleniyor"), f"BTC {fmt_usd(state['btc_fiyat'])}" if "btc_fiyat" in state else "")
    a3.metric("İzlenen Rejim", state.get("rejim", "—"), "Değişince alarm")
    a4.metric("Son Telegram", state.get("son_telegram", "Henüz alarm gönderilmedi"), "")
    if not scheduler_ok:
        st.warning("APScheduler kurulu değil — `requirements.txt`'e `apscheduler>=3.10.4` ekleyin.")
