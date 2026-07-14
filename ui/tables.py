"""İşlem günlüğü tablosu (renkli satırlarla)."""
import streamlit as st
from ui.styles import render_section_title


def _renk_kodu(gecis: str) -> str:
    g = str(gecis)
    if "Güçlü Boğa" in g and "→ Güçlü Boğa" in g:
        return "background-color:rgba(34,197,94,0.12)"
    elif "→ Boğa + Düzeltme" in g:
        return "background-color:rgba(234,179,8,0.10)"
    elif "Altın" in g or "Ayı" in g:
        return "background-color:rgba(239,68,68,0.10)"
    return ""


# Görünen tabloda gizlenecek sütunlar. Renklendirme "Geçiş" değerine göre
# yapılmaya devam eder, sadece ekrandaki tablodan kaldırılır.
GIZLI_SUTUNLAR = ["Geçiş", "Getiri"]


def render_trade_log(trade_log):
    render_section_title("8 Yıllık İşlem Günlüğü")

    gorunen_kolonlar = [c for c in trade_log.columns if c not in GIZLI_SUTUNLAR]
    gorunen_df = trade_log[gorunen_kolonlar]

    def satir_stili(row):
        gecis = trade_log.loc[row.name, "Geçiş"]
        return [_renk_kodu(gecis)] * len(row)

    st.dataframe(gorunen_df.style.apply(satir_stili, axis=1),
                 use_container_width=True, hide_index=True)
