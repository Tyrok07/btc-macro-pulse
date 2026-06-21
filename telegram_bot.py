import os
import requests
import yfinance as yf
import pandas as pd

# Şifreleri GitHub Secrets üzerinden çekiyoruz
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def rapor_gonder():
    try:
        semboller = {"GC=F": "Altın", "SI=F": "Gümüş", "HG=F": "Bakır", "BTC-USD": "Bitcoin"}
        df = yf.download(list(semboller.keys()), period="1mo", interval="1d")
        if 'Close' in df.columns:
            df = df['Close']
        df.rename(columns=semboller, inplace=True)
        df = df.ffill().bfill()
        
        df['Rasyo'] = df['Altın'] / (df['Gümüş'] + df['Bakır'])
        df['SMA20'] = df['Rasyo'].rolling(window=20).mean()
        df = df.dropna()
        
        son_rasyo = df['Rasyo'].iloc[-1]
        son_sma = df['SMA20'].iloc[-1]
        btc_fiyat = df['Bitcoin'].iloc[-1]
        
        if son_rasyo < son_sma:
            status_text = "🟢 RISK-ON (Kripto Baharı)"
        else:
            status_text = "🔴 RISK-OFF (Koruma Dönemi)"
            
        mesaj = (
            f"📊 *Günlük Makro Döngü Raporu*\n\n"
            f"🪙 *BTC Fiyatı:* ${btc_fiyat:,.2f}\n"
            f"📈 *Metal Rasyosu:* {son_rasyo:.3f}\n"
            f"📉 *Sinyal Hattı (SMA20):* {son_sma:.3f}\n\n"
            f"🚨 *Piyasa Durumu:* {status_text}\n\n"
            f"📢 _GitHub üzerinden otomatik üretilmiştir._"
        )
        
        url = f"https://telegram.org{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        print("Rapor başarıyla gönderildi!")
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    rapor_gonder()
