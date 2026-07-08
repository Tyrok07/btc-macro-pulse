from __future__ import annotations

from datetime import datetime
from importlib.util import find_spec
from pathlib import Path

from data.loader import DataLoader
from engine.regimes import RegimeDetector
from utils.alerts import load_state, save_state, send_telegram
from utils.formatters import fmt_usd

SCHEDULER_OK = find_spec("apscheduler") is not None


def check_regime_and_notify(state_file: Path, token: str, chat_id: str) -> None:
    try:
        df = DataLoader.load_recent(period="60d", interval="1d")
        if df.empty or len(df) < 52:
            return
        data = RegimeDetector().detect(df)
        last = data.iloc[-1]
        btc_price = float(last["Bitcoin"])
        gold_price = float(last["Altin"])
        btc_pct = int(last["BtcPct"])
        gold_pct = int(last["AltinPct"])
        label = last["RegimeLabel"]
        state = load_state(state_file)
        previous = state.get("rejim", "")
        if previous and previous != label:
            message = (
                f"🚨 *REJİM DEĞİŞİMİ ALARMI* 🚨\n\n"
                f"*{previous}*\n⬇️\n*{label}*\n\n"
                f"🪙 BTC: {fmt_usd(btc_price)}\n"
                f"🥇 Altın: {fmt_usd(gold_price)}\n"
                f"💼 Yeni Pozisyon: BTC %{btc_pct} · Altın %{gold_pct}\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            try:
                response = send_telegram(token, chat_id, message)
                state["son_telegram"] = "✅ Gönderildi" if response is not None and response.ok else f"❌ {response.json().get('description', 'Hata') if response is not None else 'Hata'}"
            except Exception as exc:
                state["son_telegram"] = f"❌ Bağlantı hatası: {exc}"
        state.update({
            "rejim": label,
            "son_kontrol": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "btc_fiyat": round(btc_price, 0),
            "alt_fiyat": round(gold_price, 0),
        })
        save_state(state_file, state)
    except Exception:
        pass


def start_regime_scheduler(session_state, state_file: Path, token: str, chat_id: str, interval_minutes: int) -> None:
    if SCHEDULER_OK and "scheduler_started" not in session_state:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
        scheduler.add_job(
            check_regime_and_notify,
            "interval",
            minutes=interval_minutes,
            id="rejim_kontrol",
            replace_existing=True,
            next_run_time=datetime.now(),
            args=[state_file, token, chat_id],
        )
        scheduler.start()
        session_state["scheduler_started"] = True
