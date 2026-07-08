from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Theme:
    BG: str
    CARD: str
    BORDER: str
    BORDER2: str
    TEXT: str
    TEXT2: str
    SUB: str
    MUTEDTX: str
    PLOTBG: str
    PLOTTEM: str


def get_theme(name: str = "light") -> Theme:
    if name == "dark":
        return Theme("#0B0E14", "#131722", "#1E2430", "#2A3140", "#E6E9EF", "#F2F4F8", "#7C8595", "#C8CDD8", "#0B0E14", "plotly_dark")
    return Theme("#F4F6FA", "#FFFFFF", "#E2E6EF", "#CBD2E0", "#1A1D23", "#111318", "#6B7280", "#374151", "#FFFFFF", "plotly_white")


def apply_styles(theme: Theme) -> None:
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {theme.BG}; color: {theme.TEXT}; }}
.lk-header {{ padding: 26px 4px 18px 4px; border-bottom: 1px solid {theme.BORDER}; margin-bottom: 22px; }}
.lk-eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #6FE3B5; margin-bottom: 6px; }}
.lk-title {{ font-size: 30px; font-weight: 700; color: {theme.TEXT2}; margin: 0; letter-spacing: -0.01em; }}
.lk-subtitle {{ font-size: 14px; color: {theme.SUB}; margin-top: 5px; }}
div[data-testid="stMetric"] {{ background: {theme.CARD}; border: 1px solid {theme.BORDER}; border-radius: 12px; padding: 14px 16px; }}
div[data-testid="stMetric"] label {{ color: {theme.SUB} !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.04em; }}
div[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-size: 20px !important; color: {theme.TEXT2} !important; }}
.lk-regime {{ border-radius: 12px; padding: 13px 18px; border: 1px solid; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13px; line-height: 1.6; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.lk-regime-strong-on  {{ background: rgba(34,197,94,0.12);  border-color: rgba(34,197,94,0.5);  color: #4ADE80; }}
.lk-regime-weak-on    {{ background: rgba(234,179,8,0.10);  border-color: rgba(234,179,8,0.4);  color: #F59E0B; }}
.lk-regime-weak-off   {{ background: rgba(249,115,22,0.10); border-color: rgba(249,115,22,0.4); color: #F97316; }}
.lk-regime-strong-off {{ background: rgba(239,68,68,0.10);  border-color: rgba(239,68,68,0.4);  color: #EF4444; }}
.lk-section {{ font-size: 15px; font-weight: 600; color: {theme.TEXT2}; margin: 28px 0 12px 0; padding-left: 10px; border-left: 3px solid #6FE3B5; }}
.lk-ai-box {{ background: {theme.CARD}; border: 1px solid {theme.BORDER}; border-radius: 12px; padding: 20px 24px; line-height: 1.80; font-size: 15px; color: {theme.MUTEDTX}; }}
.stButton > button {{ background: {theme.CARD}; border: 1px solid {theme.BORDER2}; color: {theme.TEXT}; border-radius: 8px; font-weight: 500; padding: 8px 18px; }}
.stButton > button:hover {{ border-color: #6FE3B5; color: #6FE3B5; }}
.stTextInput input {{ background: {theme.CARD}; border: 1px solid {theme.BORDER}; color: {theme.TEXT}; border-radius: 8px; }}
</style>
""", unsafe_allow_html=True)


def render_header() -> None:
    st.markdown("""
<div class="lk-header">
    <div class="lk-eyebrow">XAUUSD / XCUUSD / BTCUSD · Likidite Kompoziti · 8 Yıllık Analiz</div>
    <p class="lk-title">Süper Kompozit Likidite Paneli</p>
    <p class="lk-subtitle">Altın · Bakır · Bitcoin rasyosu üzerinden küresel likidite yönünü ve fırsatları takip et</p>
</div>
""", unsafe_allow_html=True)


def render_section(title: str) -> None:
    st.markdown(f'<div class="lk-section">{title}</div>', unsafe_allow_html=True)
