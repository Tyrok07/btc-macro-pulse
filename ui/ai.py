from __future__ import annotations

import requests
import streamlit as st

from utils.formatters import fmt_pct


def gemini_api(api_key: str, prompt: str) -> str | None:
    if not api_key:
        return None
    for model in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if response.status_code == 429:
                continue
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    return None


@st.cache_data(ttl=1800)
def gemini_yorum_cache(api_key: str, btc_r: float, rejim: str, rot_k: float, bh_btc_k: float, bh_alt_k: float, kisa_bull: bool, makro_bull: bool) -> str | None:
    prompt = f"""
Sen bir makro piyasa analistisin. Aşağıdaki verilere bakarak sıradan bir yatırımcının
anlayabileceği sade Türkçe ile 4-6 cümlelik özet yorum yaz. Teknik jargon kullanma.
Sonunda tek cümleyle "Şu an ne yapmalı?" önerisi ver.

- Bitcoin: ${btc_r:,.0f}
- Rejim: {rejim}
- Kısa vade (SMA10): {"Boğa" if kisa_bull else "Ayı"}
- Uzun vade (SMA50): {"Boğa" if makro_bull else "Ayı"}
- 8Y Rotasyon kazancı: {fmt_pct(rot_k)}
- BTC al-tut kıyası: {fmt_pct(bh_btc_k)}
- Altın al-tut kıyası: {fmt_pct(bh_alt_k)}

Sadece yorum metni yaz, madde işareti veya başlık ekleme.
"""
    return gemini_api(api_key, prompt)
