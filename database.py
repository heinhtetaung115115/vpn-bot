"""
database.py — PostgreSQL database for VPN bot (Railway-ready)
"""

import os
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

def _conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def init_db():
    """Create all tables on startup."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     BIGINT PRIMARY KEY,
                    username    TEXT,
                    balance     NUMERIC(12,2) DEFAULT 0,
                    joined      TEXT
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id          SERIAL PRIMARY KEY,
                    user_id     BIGINT,
                    type        TEXT,
                    amount      NUMERIC(12,2),
                    note        TEXT,
                    date        TEXT
                );
                CREATE TABLE IF NOT EXISTS stock (
                    id          TEXT PRIMARY KEY,
                    stock_key   TEXT,
                    details     TEXT,
                    note        TEXT DEFAULT '',
                    added       TEXT,
                    sold        BOOLEAN DEFAULT FALSE
                );
                CREATE TABLE IF NOT EXISTS orders (
                    order_id    TEXT PRIMARY KEY,
                    user_id     BIGINT,
                    brand_id    TEXT,
                    plan_id     TEXT,
                    amount      NUMERIC(12,2),
                    details     TEXT,
                    acct_note   TEXT DEFAULT '',
                    date        TEXT
                );
                CREATE TABLE IF NOT EXISTS topup_requests (
                    request_id  TEXT PRIMARY KEY,
                    user_id     BIGINT,
                    amount      NUMERIC(12,2),
                    method      TEXT,
                    note        TEXT,
                    status      TEXT DEFAULT 'pending',
                    date        TEXT
                );
                CREATE TABLE IF NOT EXISTS short_ids (
                    short_id    TEXT PRIMARY KEY,
                    full_id     TEXT
                );
            """)
        conn.commit()


class Database:

    # ── Users ─────────────────────────────────────────────────────────────
    def ensure_user(self, user_id: int, username: str):
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, balance, joined)
                    VALUES (%s, %s, 0, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id, username, _now()))
            conn.commit()

    def get_user(self, user_id: int) -> dict:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return dict(row) if row else {}

    def deduct_balance(self, user_id: int, amount: float):
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (amount, user_id))
                cur.execute("""INSERT INTO transactions (user_id, type, amount, note, date)
                               VALUES (%s, 'purchase', %s, %s, %s)""",
                            (user_id, amount, "VPN ဝယ်ယူမှု", _now()))
            conn.commit()

    def get_transactions(self, user_id: int, limit: int = 10) -> list:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                            (user_id, limit))
                return [dict(r) for r in cur.fetchall()]

    # ── Short ID mapping ──────────────────────────────────────────────────
    def register_short_id(self, short_id: str, full_id: str):
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO short_ids (short_id, full_id) VALUES (%s, %s)
                               ON CONFLICT (short_id) DO UPDATE SET full_id = EXCLUDED.full_id""",
                            (short_id, full_id))
            conn.commit()

    def resolve_short_id(self, short_id: str):
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT full_id FROM short_ids WHERE short_id = %s", (short_id,))
                row = cur.fetchone()
                return row["full_id"] if row else None

    # ── Stock ─────────────────────────────────────────────────────────────
    def add_account(self, stock_key: str, details: str, note: str = ""):
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO stock (id, stock_key, details, note, added, sold)
                               VALUES (%s, %s, %s, %s, %s, FALSE)""",
                            (str(uuid.uuid4())[:8], stock_key, details, note, _now()))
            conn.commit()

    def pop_account(self, stock_key: str) -> dict | None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT * FROM stock WHERE stock_key = %s AND sold = FALSE
                               ORDER BY added LIMIT 1""", (stock_key,))
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute("UPDATE stock SET sold = TRUE WHERE id = %s", (row["id"],))
            conn.commit()
            return dict(row)

    def get_stock_count(self, stock_key: str) -> int:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM stock WHERE stock_key = %s AND sold = FALSE",
                            (stock_key,))
                return cur.fetchone()["cnt"]

    # ── Orders ────────────────────────────────────────────────────────────
    def create_order(self, user_id: int, brand_id: str, plan_id: str, plan: dict, account: dict) -> str:
        order_id = str(uuid.uuid4())
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO orders (order_id, user_id, brand_id, plan_id, amount, details, acct_note, date)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (order_id, user_id, brand_id, plan_id, plan["price"],
                             account["details"], account.get("note", ""), _now()))
            conn.commit()
        return order_id

    def get_orders(self, user_id: int) -> list:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY date DESC LIMIT 10",
                            (user_id,))
                return [dict(r) for r in cur.fetchall()]

    # ── Top-up Requests ───────────────────────────────────────────────────
    def create_topup_request(self, user_id: int, amount: float, method: str, note: str) -> str:
        req_id = str(uuid.uuid4())
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO topup_requests (request_id, user_id, amount, method, note, status, date)
                               VALUES (%s,%s,%s,%s,%s,'pending',%s)""",
                            (req_id, user_id, amount, method, note, _now()))
            conn.commit()
        return req_id

    def get_topup_request(self, req_id: str) -> dict | None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM topup_requests WHERE request_id = %s", (req_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def approve_topup(self, req_id: str) -> bool:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM topup_requests WHERE request_id = %s", (req_id,))
                req = cur.fetchone()
                if not req:
                    return False
                cur.execute("UPDATE topup_requests SET status = 'approved' WHERE request_id = %s", (req_id,))
                # Upsert user balance — works even if user somehow missing
                cur.execute("""INSERT INTO users (user_id, username, balance, joined)
                               VALUES (%s, 'unknown', %s, %s)
                               ON CONFLICT (user_id) DO UPDATE SET balance = users.balance + EXCLUDED.balance""",
                            (req["user_id"], req["amount"], _now()))
                cur.execute("""INSERT INTO transactions (user_id, type, amount, note, date)
                               VALUES (%s, 'topup', %s, %s, %s)""",
                            (req["user_id"], req["amount"],
                             f"ငွေဖြည့်မှုအတည်ပြုပြီး ({req['method']})", _now()))
            conn.commit()
            return True

    def reject_topup(self, req_id: str) -> bool:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE topup_requests SET status = 'rejected' WHERE request_id = %s", (req_id,))
            conn.commit()
            return True

    def get_pending_topups(self) -> list:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM topup_requests WHERE status = 'pending' ORDER BY date")
                return [dict(r) for r in cur.fetchall()]

    # ── Stats ─────────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM users")
                users = cur.fetchone()["cnt"]
                cur.execute("SELECT COUNT(*) as cnt FROM orders")
                orders = cur.fetchone()["cnt"]
                cur.execute("SELECT COALESCE(SUM(amount),0) as total FROM orders")
                revenue = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) as cnt FROM topup_requests WHERE status='pending'")
                pending = cur.fetchone()["cnt"]
                return {"users": users, "orders": orders,
                        "revenue": float(revenue), "pending_topups": pending}


db = Database()
