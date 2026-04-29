# ──────────────────────────────────────────────
#  config.py — Bot Configuration
# ──────────────────────────────────────────────

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_IDS = [123456789]
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

# ──────────────────────────────────────────────
#  VPN Products
#
#  Structure:
#    VPN_PRODUCTS = {
#      "brand_id": {
#        "name": "Display Name",
#        "emoji": "emoji",
#        "description": "short description",
#        "plans": {
#          "plan_id": {"name": "...", "duration_days": N, "price": N}
#        }
#      }
#    }
#
#  Stock key = "brand_id:plan_id"  e.g. "expressvpn:1month"
# ──────────────────────────────────────────────
VPN_PRODUCTS = {
    "expressvpn": {
        "name": "ExpressVPN",
        "emoji": "⚡",
        "description": "Fast & secure VPN",
        "plans": {
            "1month":  {"name": "1 Month",  "duration_days": 30,  "price": 5000},
            "6month":  {"name": "6 Months", "duration_days": 180, "price": 25000},
            "1year":   {"name": "1 Year",   "duration_days": 365, "price": 45000},
        },
    },
    "adguard": {
        "name": "AdGuard VPN",
        "emoji": "🛡️",
        "description": "Privacy & ad-blocking VPN",
        "plans": {
            "1month":  {"name": "1 Month",  "duration_days": 30,  "price": 3000},
            "6month":  {"name": "6 Months", "duration_days": 180, "price": 15000},
        },
    },
    "nordvpn": {
        "name": "NordVPN",
        "emoji": "🔵",
        "description": "Top-rated security VPN",
        "plans": {
            "1month":  {"name": "1 Month",  "duration_days": 30,  "price": 6000},
            "6month":  {"name": "6 Months", "duration_days": 180, "price": 30000},
            "1year":   {"name": "1 Year",   "duration_days": 365, "price": 50000},
        },
    },
}
