from __future__ import annotations

import pandas as pd
import streamlit as st


def _trade_row_style(row: pd.Series) -> list[str]:
    transition = str(row.get("Geçiş", ""))
    if "Güçlü Boğa" in transition and "→ Güçlü Boğa" in transition:
        return ["background-color:rgba(34,197,94,0.12)"] * len(row)
    if "→ Boğa + Düzeltme" in transition:
        return ["background-color:rgba(234,179,8,0.10)"] * len(row)
    if "Altın" in transition or "Ayı" in transition:
        return ["background-color:rgba(239,68,68,0.10)"] * len(row)
    return [""] * len(row)


def render_trade_log(trade_log: pd.DataFrame) -> None:
    st.dataframe(trade_log.style.apply(_trade_row_style, axis=1), use_container_width=True, hide_index=True)


def trade_summary_text(trade_log: pd.DataFrame, fmt_usd) -> str:
    if trade_log.empty:
        return "İşlem günlüğü boş."
    best = trade_log.loc[trade_log["Getiri"].idxmax()]
    worst = trade_log.loc[trade_log["Getiri"].idxmin()]
    return (
        f"8 yılda toplam {len(trade_log)} rejim geçişi yaşandı.\n"
        f"En yüksek getiri: {best['Tarih']} tarihinde {best['Geçiş']} "
        f"geçişiyle portföy {fmt_usd(best['Portföy'])} oldu (%{best['Getiri']:+.1f}).\n"
        f"En düşük getiri: {worst['Tarih']} tarihinde {worst['Geçiş']} "
        f"geçişiyle portföy {fmt_usd(worst['Portföy'])} oldu (%{worst['Getiri']:+.1f}).\n"
        f"Son işlem: {trade_log.iloc[-1]['Tarih']} — {trade_log.iloc[-1]['Geçiş']}."
    )
