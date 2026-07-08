diff --git a/ui/assistant_panel.py b/ui/assistant_panel.py
new file mode 100644
index 0000000000000000000000000000000000000000..bf0d33f04712bff3c3b077736df328ffeff6558a
--- /dev/null
+++ b/ui/assistant_panel.py
@@ -0,0 +1,107 @@
+from __future__ import annotations
+
+from datetime import datetime
+
+import streamlit as st
+
+from ui.tables import trade_summary_text
+from utils.ai import gemini_api, gemini_yorum_cache
+from utils.alerts import send_telegram
+from utils.formatters import fmt_pct, fmt_usd
+
+
+def render_ai_commentary(api_key: str, last, stats: dict, trade_log) -> None:
+    if api_key:
+        with st.spinner("Piyasa verileri yorumlanıyor..."):
+            yorum = gemini_yorum_cache(
+                api_key,
+                round(float(last["Bitcoin"]) / 500) * 500,
+                last["RegimeLabel"],
+                stats["rot_kazanc"],
+                stats["bh_btc_k"],
+                stats["bh_alt_k"],
+                bool(last["ShortBull"]),
+                bool(last["MacroBull"]),
+            )
+        if yorum:
+            st.markdown(f'<div class="lk-ai-box">{yorum}</div>', unsafe_allow_html=True)
+        else:
+            st.info("Otomatik yorum şu an alınamadı (rate limit). 30 dakika sonra yenilenir.")
+    else:
+        st.info("Otomatik yorum için `GEMINI_API_KEY` ekleyin — Ücretsiz: aistudio.google.com")
+
+    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
+    question = st.text_input("", placeholder="İşlem günlüğü, rejim veya strateji hakkında bir soru sorun...", label_visibility="collapsed")
+    if question and api_key:
+        with st.spinner("Yanıt hazırlanıyor..."):
+            answer = gemini_api(api_key, _question_prompt(question, last, stats, trade_log))
+            if answer:
+                st.markdown(f'<div class="lk-ai-box">{answer}</div>', unsafe_allow_html=True)
+    elif question and not api_key:
+        st.info("`GEMINI_API_KEY` olmadan soru yanıtlanamaz.")
+
+
+def render_manual_telegram(token: str, chat_id: str, last, stats: dict) -> None:
+    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
+    if st.button("📲 Güncel Durumu Telegram'a Gönder"):
+        if not token:
+            st.error("TELEGRAM_TOKEN eksik — Streamlit secrets'a ekleyin.")
+        elif not chat_id:
+            st.error("TELEGRAM_CHAT_ID eksik — Streamlit secrets'a ekleyin.")
+        else:
+            _send_report(token, chat_id, last, stats)
+
+
+def _question_prompt(question: str, last, stats: dict, trade_log) -> str:
+    trade_summary = trade_summary_text(trade_log, fmt_usd)
+    return f"""
+Sen bir piyasa analisti danışmanısın. Aşağıdaki verilere dayanarak soruyu yanıtla.
+Sıradan bir yatırımcıya sade Türkçe, kısa ve net yanıt ver. Teknik jargon kullanma.
+
+MEVCUT DURUM:
+- BTC: {fmt_usd(float(last['Bitcoin']))} | Altın: {fmt_usd(float(last['Altin']))}
+- Rejim: {last['RegimeLabel']}
+- Kısa vade: {"Boğa" if bool(last['ShortBull']) else "Ayı"} | Uzun vade: {"Boğa" if bool(last['MacroBull']) else "Ayı"}
+- Şu an pozisyon: BTC %{int(last['BtcPct'])} · Altın %{int(last['AltinPct'])}
+
+PORTFÖY PERFORMANSI:
+- 8Y Rotasyon: {fmt_pct(stats['rot_kazanc'])} ({fmt_usd(stats['rot_son'])})
+- BTC al-tut: {fmt_pct(stats['bh_btc_k'])} ({fmt_usd(stats['bh_btc_son'])})
+- Altın al-tut: {fmt_pct(stats['bh_alt_k'])} ({fmt_usd(stats['bh_alt_son'])})
+- Maks. Drawdown: {fmt_pct(stats['max_dd'])}
+- BTC'de geçen süre: {stats['btc_gun']} gün | Altın'da: {stats['alt_gun']} gün
+
+İŞLEM GEÇMİŞİ ÖZETİ:
+{trade_summary}
+
+Soru: {question}
+"""
+
+
+def _send_report(token: str, chat_id: str, last, stats: dict) -> None:
+    report = (
+        f"◆ *LİKİDİTE KOMPOZİT PANELİ* ◆\n\n"
+        f"🪙 BTC: {fmt_usd(float(last['Bitcoin']))} ({fmt_pct(stats['btc_degisim'])} gün)\n"
+        f"🥇 Altın: {fmt_usd(float(last['Altin']))} ({fmt_pct(stats['alt_degisim'])} gün)\n\n"
+        f"📊 Rejim: *{last['RegimeLabel']}*\n"
+        f"  • Kısa Vade: {'🟢 Boğa' if bool(last['ShortBull']) else '🔴 Ayı'}\n"
+        f"  • Uzun Vade: {'🟢 Boğa' if bool(last['MacroBull']) else '🔴 Ayı'}\n\n"
+        f"💼 Pozisyon: BTC %{int(last['BtcPct'])} · Altın %{int(last['AltinPct'])}\n\n"
+        f"📈 8Y Rotasyon:   {fmt_usd(stats['rot_son'])} ({fmt_pct(stats['rot_kazanc'])})\n"
+        f"₿  BTC Al-Tut:   {fmt_usd(stats['bh_btc_son'])} ({fmt_pct(stats['bh_btc_k'])})\n"
+        f"🥇 Altın Al-Tut:  {fmt_usd(stats['bh_alt_son'])} ({fmt_pct(stats['bh_alt_k'])})\n\n"
+        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
+    )
+    try:
+        response = send_telegram(token, chat_id, report)
+        if response is not None and response.ok:
+            st.success("Telegram'a gönderildi.")
+        else:
+            error = response.json().get("description", response.text) if response is not None else "Telegram bilgileri eksik"
+            st.error(f"Telegram hatası: {error}")
+            if "chat was deleted" in error or "chat not found" in error.lower():
+                st.info("💡 **Çözüm:** Grup silinmiş. Kişisel chat ID'nizi kullanın:\n\n1. Telegram'da `@userinfobot` botunu açın\n2. `/start` yazın → size kişisel ID'nizi verir\n3. Streamlit secrets'ta `TELEGRAM_CHAT_ID` değerini bu ID ile güncelleyin")
+            elif "Unauthorized" in error or "bot was blocked" in error:
+                st.info("💡 **Çözüm:** Bot token geçersiz veya bloklanmış.\n\n1. `@BotFather`'da `/mybots` → botunuzu seçin → `API Token`\n2. Streamlit secrets'ta `TELEGRAM_TOKEN` değerini güncelleyin")
+    except Exception as exc:
+        st.error(f"Bağlantı hatası: {exc}")
