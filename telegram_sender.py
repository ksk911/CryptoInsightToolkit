# In telegram_sender.py

import requests
import json
from datetime import datetime
from typing import Optional

# --- 🛑 FINAL CONFIGURATION 🛑 ---
# Use the strings obtained from BotFather and the getUpdates URL
BOT_TOKEN: str = "8461651460:AAGLtyh7IEUPnVjiJqsqgIOsEw9XhMxdQ6Y" 
CHAT_ID: str = "5058519218"           # <--- YOUR CHAT ID IS HERE
# ------------------------------------

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram_message(message: str):
    """Sends a message to the configured Telegram chat ID."""
    
    # We remove the API key check here as it is now configured
    
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown' # Using Markdown for basic formatting
    }
    
    try:
        response = requests.post(TELEGRAM_API_URL, data=payload)
        response.raise_for_status()
        print(f"✅ Telegram Alert Sent at {datetime.now().strftime('%H:%M:%S')}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Telegram Communication Error: {e}")


if __name__ == "__main__":
    # RUN THIS SCRIPT TO TEST THE INTEGRATION!
    test_message = "*TEST ALERT: Telegram Integration Successful!*"
    send_telegram_message(test_message)