import os

# ──────────────────────────────────────────────
#  config.py — Bot Configuration (Railway)
# ──────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "123456789").split(",")]
CURRENCY = "ks"
MIN_TOPUP = 1000.0

# ──────────────────────────────────────────────
#  Payment Methods
# ──────────────────────────────────────────────
PAYMENT_METHODS = {
    "kbzpay": {
        "name": "KBZ Pay",
        "emoji": "🏦",
        "description": "Transfer via KBZ Pay",
        "payment_info": "KBZ Pay Number:\n📱 09-XXXXXXXXX\n\nAccount Name: YOUR NAME",
    },
    "wavepay": {
        "name": "Wave Pay",
        "emoji": "🌊",
        "description": "Transfer via Wave Pay",
        "payment_info": "Wave Pay Number:\n📱 09-XXXXXXXXX\n\nAccount Name: YOUR NAME",
    },
    "ayapay": {
        "name": "AYA Pay",
        "emoji": "💳",
        "description": "Transfer via AYA Pay",
        "payment_info": "AYA Pay Number:\n📱 09-XXXXXXXXX\n\nAccount Name: YOUR NAME",
    },
}
  
