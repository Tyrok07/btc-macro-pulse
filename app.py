from __future__ import annotations

from pathlib import Path

import streamlit as st

from data.loader import DataLoader
from data.preprocess import preprocess, validate_market_data
from engine.backtest import BacktestEngine
from ui.assistant_panel import render_ai_commentary, render_manual_telegram
from ui.cards import (
    render_alarm_status,
    render_benchmark_message,
    render_performance_metrics,
    render_regime_banner,
    render_top_metrics,
)
from ui.charts import (
    render_allocation_chart,
    render_liquidity_chart,
    render_portfolio_comparison_chart,
)
from ui.styles import apply_styles, get_theme, render_header, render_section
from ui.tables import render_trade_log
from utils.alerts import load_state
from utils.scheduler import SCHEDULER_OK, start_regime_scheduler


st.set_page_config(page_title="Likidite Kompozit Paneli", layout="wide", page_icon="◆")

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)
ALERT_STATE_FILE = STATE_DIR / "alert_state.json"
KONTROL_ARALIK = 140
TEMA = "light"

GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
TOKEN = str(st.secrets.get("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()


def main() -> None:
    theme = get_theme(TEMA)
    apply_styles(theme)
    render_header()
    start_regime_scheduler(st.session_state, ALERT_STATE_FILE, TOKEN, CHAT_ID, KONTROL_ARALIK)

    raw = DataLoader.load()
    error = validate_market_data(raw)
    if error:
        st.error(error)
        st.stop()

    market_data = preprocess(raw)
    result = BacktestEngine().run(market_data)
    data = result.data
    trade_log = result.trade_log
    stats = result.stats
    last = data.iloc[-1]

    render_top_metrics(last, stats)
    render_regime_banner(last)
    render_benchmark_message(stats)

    render_section("Strateji Performans İstatistikleri")
    render_performance_metrics(stats)

    render_section("Likidite Rasyosu · SMA10 · SMA50 · BTC Fiyatı")
    render_liquidity_chart(data, theme)

    render_section("Portföy Karşılaştırma · Rotasyon vs BTC Al-Tut vs Altın Al-Tut")
    render_portfolio_comparison_chart(data, theme)

    render_section("Portföy Dağılımı · BTC vs Altın Ağırlığı")
    render_allocation_chart(data, theme)

    render_section("8 Yıllık İşlem Günlüğü")
    render_trade_log(trade_log)

    render_section("Otomatik Alarm Sistemi · 7/24")
    render_alarm_status(load_state(ALERT_STATE_FILE), KONTROL_ARALIK, SCHEDULER_OK)

    render_section("Yapay Zeka Piyasa Yorumu")
    render_ai_commentary(GEMINI_KEY, last, stats, trade_log)
    render_manual_telegram(TOKEN, CHAT_ID, last, stats)


try:
    main()
except Exception as exc:
    import traceback

    st.error(f"Genel hata: {exc}")
    st.code(traceback.format_exc())
