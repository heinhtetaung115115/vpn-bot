"""
products.py — Load/save VPN products from products.json
All brand & plan management goes through here.
"""

import json
import os
from threading import Lock

PRODUCTS_FILE = "products.json"
_lock = Lock()


def load() -> dict:
    if not os.path.exists(PRODUCTS_FILE):
        return {}
    with open(PRODUCTS_FILE, "r") as f:
        return json.load(f)


def save(data: dict):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Brand ────────────────────────────────────────────────────────────────────

def get_all() -> dict:
    return load()

def get_brand(brand_id: str) -> dict | None:
    return load().get(brand_id)

def add_brand(brand_id: str, name: str, emoji: str, description: str) -> bool:
    with _lock:
        data = load()
        if brand_id in data:
            return False  # already exists
        data[brand_id] = {"name": name, "emoji": emoji, "description": description, "plans": {}}
        save(data)
        return True

def remove_brand(brand_id: str) -> bool:
    with _lock:
        data = load()
        if brand_id not in data:
            return False
        del data[brand_id]
        save(data)
        return True

def update_brand(brand_id: str, **kwargs) -> bool:
    with _lock:
        data = load()
        if brand_id not in data:
            return False
        for k, v in kwargs.items():
            if k in ("name", "emoji", "description"):
                data[brand_id][k] = v
        save(data)
        return True


# ── Plan ─────────────────────────────────────────────────────────────────────

def add_plan(brand_id: str, plan_id: str, name: str, duration_days: int, price: int) -> bool:
    with _lock:
        data = load()
        if brand_id not in data:
            return False
        data[brand_id]["plans"][plan_id] = {
            "name": name,
            "duration_days": duration_days,
            "price": price,
        }
        save(data)
        return True

def remove_plan(brand_id: str, plan_id: str) -> bool:
    with _lock:
        data = load()
        if brand_id not in data:
            return False
        if plan_id not in data[brand_id]["plans"]:
            return False
        del data[brand_id]["plans"][plan_id]
        save(data)
        return True
