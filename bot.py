from flask import Flask, request, jsonify
import requests
import re
import time
import random
import logging
from bs4 import BeautifulSoup

# ------------------------------
# CONFIGURATION
# ------------------------------
BOT_TOKEN = "8337001479:AAGPsETwLD2LSi-MX9g9-XMUdJVDNDd6y0s"  # REPLACE WITH YOUR NEW TOKEN
PHONE_PREFIX = "91"
LINK_SAVE_FILE = "gemini_links.txt"

# ------------------------------
# LOGGING
# ------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------
# FLASK APP
# ------------------------------
app = Flask(__name__)

# ------------------------------
# TELEGRAM WEBHOOK SETUP
# ------------------------------
WEBHOOK_URL = "https://gemini-bot1.onrender.com/webhook"  # REPLACE WITH YOUR RENDER URL

def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    response = requests.post(url, json={"url": WEBHOOK_URL})
    logger.info(f"Webhook set: {response.json()}")

# ------------------------------
# SMS SITES (10+ FREE)
# ------------------------------
SMS_SITES = [
    {"name": "receive-sms-online", "url": "https://receive-sms-online.info", "number_selector": "a[href*='phone']", "message_selector": "div.sms-message, div.message, li.message, div.msg", "otp_pattern": r'\b\d{6}\b'},
    {"name": "smsreceivefree", "url": "https://smsreceivefree.com", "number_selector": "a[href*='number']", "message_selector": "div.sms, div.message, td.message, div.msg", "otp_pattern": r'\b\d{6}\b'},
    {"name": "quackr", "url": "https://quackr.io", "number_selector": "a[href*='/number/']", "message_selector": "div.message, div.sms, li.msg", "otp_pattern": r'\b\d{6}\b'},
    {"name": "temp-number", "url": "https://temp-number.com", "number_selector": "a[href*='phone']", "message_selector": "div.sms, div.message, td.sms", "otp_pattern": r'\b\d{6}\b'},
    {"name": "receive-sms.cc", "url": "https://receive-sms.cc", "number_selector": "a[href*='number']", "message_selector": "div.sms, div.message, div.msg", "otp_pattern": r'\b\d{6}\b'},
    {"name": "sms-online.co", "url": "https://sms-online.co", "number_selector": "a[href*='receive']", "message_selector": "div.sms, div.message, tr.message", "otp_pattern": r'\b\d{6}\b'},
    {"name": "receivesmsonline.net", "url": "https://receivesmsonline.net", "number_selector": "a[href*='phone']", "message_selector": "div.sms, div.message, li.msg", "otp_pattern": r'\b\d{6}\b'},
    {"name": "textnow", "url": "https://textnow.com", "number_selector": "a[href*='number']", "message_selector": "div.message, div.sms, li.conversation", "otp_pattern": r'\b\d{6}\b'},
    {"name": "receive-sms-online.com", "url": "https://receive-sms-online.com", "number_selector": "a[href*='phone']", "message_selector": "div.sms, div.message, td.message", "otp_pattern": r'\b\d{6}\b'},
    {"name": "smslist24", "url": "https://smslist24.com", "number_selector": "a[href*='number']", "message_selector": "div.sms, div.message, div.msg", "otp_pattern": r'\b\d{6}\b'}
]

# ------------------------------
# PHONE & OTP EXTRACTION
# ------------------------------
def get_phone_from_site(site):
    try:
        resp = requests.get(site["url"], timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        elements = soup.select(site["number_selector"])
        for el in elements:
            raw = el.text.strip()
            cleaned = re.sub(r'\D', '', raw)
            if len(cleaned) >= 10 and cleaned[0] in '6789':
                return cleaned[-10:]
        return None
    except Exception as e:
        logger.warning(f"[{site['name']}] Failed to get number: {e}")
        return None

def get_otp_from_site(site, phone_number):
    try:
        url = f"{site['url']}/phone/{phone_number}" if 'phone' in site['url'] else f"{site['url']}/number/{phone_number}"
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        messages = soup.select(site["message_selector"])
        for msg in messages:
            text = msg.text.lower()
            if any(kw in text for kw in ['otp', 'code', 'verification', 'pin', 'passcode']):
                otp_match = re.search(site["otp_pattern"], text)
                if otp_match:
                    return otp_match.group(0)
        return None
    except Exception as e:
        logger.warning(f"[{site['name']}] Failed to get OTP: {e}")
        return None

def get_free_phone_number():
    shuffled = random.sample(SMS_SITES, len(SMS_SITES))
    for site in shuffled:
        phone = get_phone_from_site(site)
        if phone:
            return phone, site
    return None, None

def get_otp_with_fallback(phone_number, max_attempts=15):
    for attempt in range(max_attempts):
        for site in random.sample(SMS_SITES, len(SMS_SITES)):
            otp = get_otp_from_site(site, phone_number)
            if otp:
                return otp
        time.sleep(3)
    return None

# ------------------------------
# GOOGLE ACTIVATION API
# ------------------------------
def request_otp(phone_number, device_id):
    url = "https://serviceactivation.google.com/subscription/request_otp"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Device-ID": device_id,
        "Content-Type": "application/json"
    }
    payload = {"phone": f"+{PHONE_PREFIX}{phone_number}", "device_id": device_id, "source": "jio_gemini_offer"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def verify_otp(phone_number, otp, device_id):
    url = "https://serviceactivation.google.com/subscription/verify_otp"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Device-ID": device_id,
        "Content-Type": "application/json"
    }
    payload = {"phone": f"+{PHONE_PREFIX}{phone_number}", "otp": otp, "device_id": device_id}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        data = resp.json()
        return data.get("activation_url")
    except Exception:
        return None

# ------------------------------
# GENERATE LINK
# ------------------------------
def generate_free_link():
    device_id = ''.join(random.choices('0123456789abcdef', k=16))
    phone, used_site = get_free_phone_number()
    if not phone:
        return "❌ No free phone number available."

    otp_resp = request_otp(phone, device_id)
    if otp_resp.get("status") != "otp_sent":
        return f"❌ OTP request failed: {otp_resp.get('message', 'Unknown error')}"

    otp = get_otp_with_fallback(phone)
    if not otp:
        return "❌ OTP not found."

    link = verify_otp(phone, otp, device_id)
    if link:
        with open(LINK_SAVE_FILE, "a") as f:
            f.write(link + "\n")
        return f"✅ LINK FOUND!\n\n{link}\n\nPhone: +{PHONE_PREFIX}{phone}\nOTP: {otp}"
    else:
        return "❌ Verification failed."

# ------------------------------
# TELEGRAM WEBHOOK HANDLER
# ------------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return 'OK', 200

    chat_id = data['message']['chat']['id']
    text = data['message'].get('text', '')

    if text == '/start':
        send_message(chat_id, "🤖 Gemini Link Generator\n\nSend /generate to get a link.")
    elif text == '/generate':
        msg = send_message(chat_id, "⏳ Generating link...")
        result = generate_free_link()
        send_message(chat_id, result)
    elif text == '/status':
        try:
            with open(LINK_SAVE_FILE, "r") as f:
                count = len(f.readlines())
            send_message(chat_id, f"📊 Total links: {count}")
        except:
            send_message(chat_id, "📊 No links yet.")
    elif text == '/export':
        try:
            with open(LINK_SAVE_FILE, "rb") as f:
                files = {'document': f}
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument", data={'chat_id': chat_id}, files=files)
        except:
            send_message(chat_id, "❌ No links file found.")
    else:
        send_message(chat_id, "Unknown command. Use /start, /generate, /status, /export")

    return 'OK', 200

# ------------------------------
# HELPERS
# ------------------------------
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    return requests.post(url, json=payload).json()

# ------------------------------
# HOME
# ------------------------------
@app.route('/')
def home():
    return "🤖 Gemini Bot is running!"

# ------------------------------
# START
# ------------------------------
if __name__ == "__main__":
    set_webhook()
    app.run(host='0.0.0.0', port=10000)
