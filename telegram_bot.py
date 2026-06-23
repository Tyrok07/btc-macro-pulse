import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# ====================== AYARLAR ======================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("HATA: TELEGRAM_TOKEN veya TELEGRAM_CHAT_ID environment variable bulunamadı!")
    exit(1)

def rapor_gonder():
    try:
        semboller = {"GC=F": "Altın", "SI=F": "Gümüş", "HG=F": "Bakır", "BTC-USD": "Bitcoin"}
        
        # Daha stabil veri çekme
        df = yf.download(
            list(semboller.keys()), 
            period="40d",          # 1 ay yerine biraz daha fazla güvenlik için
            interval="1d", 
            progress=False,
            auto_adjust=True
        )

        # MultiIndex düzeltme (yfinance'ın yeni yapısı)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs('Close', axis=1, level=1)
        else:
            df = df['Close'] if 'Close' in df.columns else df

        df = df.rename(columns=semboller)
        df = df.ffill().bfill()

        if len(df) < 20:
            print("HATA: Yeterli veri çekilemedi.")
            return

        # ==================== HESAPLAMALAR ====================
        df['Rasyo'] = df['Altın'] / (df['Gümüş'] + df['Bakır'] + 1e-8)  # sıfıra bölme koruması
        df['SMA20'] = df['Rasyo'].rolling(window=20).mean()
        df = df.dropna()

        son_rasyo = df['Rasyo'].iloc[-1]
        son_sma = df['SMA20'].iloc[-1]
        btc_fiyat = df['Bitcoin'].iloc[-1]
        btc_degisim = (df['Bitcoin'].iloc[-1] / df['Bitcoin'].iloc[-2] - 1) * 100

        # Rejim tespiti
        if son_rasyo < son_sma:
            status_text = "🟢 RISK-ON (Kripto Baharı)"
            status_emoji = "🚀"
        else:
            status_text = "🔴 RISK-OFF (Koruma Dönemi)"
            status_emoji = "🛡️"

        # ==================== MESAJ ====================
        mesaj = (
            f"📊 *Günlük Makro Döngü Raporu*\n"
            f"⏰ `{datetime.now().strftime('%d.%m.%Y %H:%M')}`\n\n"
            f"🪙 *Bitcoin:* `${btc_fiyat:,.2f}` ({btc_degisim:+.2f}%)\n"
            f"📈 *Metal Rasyosu:* `{son_rasyo:.4f}`\n"
            f"📉 *SMA20 Sinyal Hattı:* `{son_sma:.4f}`\n\n"
            f"{status_emoji} *Durum:* {status_text}\n\n"
            f"———\n"
            f"_GitHub Actions ile otomatik gönderilmiştir._"
        )

        # Telegram Gönderimi
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": mesaj,
            "parse_mode": "Markdown"
        }

        response = requests.post(url, json=payload, timeout=15)

        if response.status_code == 200:
            print("✅ Rapor başarıyla Telegram'a gönderildi!")
        else:
            print(f"❌ Telegram API Hatası: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Genel Hata: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    rapor_gonder()
