"""
SpendShield AI — stdlib-only dev server  [LEGACY / OPTIONAL]
=============================================================
Historical note: this existed because the sandbox that first generated this
project had no outbound network access, so `pip install fastapi` was impossible
and there was no other way to demonstrate the money logic running over HTTP.

That constraint no longer applies. The real FastAPI app installs, runs, and is
covered by 59 tests (`pytest`), so this file is no longer the proof that the
project works — `app/` is. It is kept only as a zero-dependency fallback for
environments where installing the requirements genuinely isn't an option.

Be aware it is a PARALLEL implementation and has drifted from the real API:
it takes credentials as query parameters and issues opaque random tokens
rather than JWTs. Do not treat its request/response shapes as the contract —
`app/main.py` and /docs are the contract. It does still import the same
`app/services/*` engines, so the money math it reports is the real math.

Run: python3 devserver.py     ->  http://localhost:8787/health
"""

import calendar
import hashlib
import json
import os
import secrets
import sqlite3
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.forecasting import (
    DailySpend,
    calculate_spending_velocity,
    forecast_month_end_spend,
)
from app.services.impulse_score import ImpulseInput
from app.services.impulse_score import evaluate as evaluate_impulse
from app.services.intervention import InterventionInput
from app.services.intervention import decide as decide_intervention
from app.services.safe_to_spend import SafeToSpendInput, calculate_safe_to_spend, evaluate_purchase

DB_PATH = os.path.join(os.path.dirname(__file__), "devserver.sqlite3")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month INTEGER NOT NULL,
        year INTEGER NOT NULL,
        total_income REAL NOT NULL,
        savings_target REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        merchant TEXT,
        category TEXT NOT NULL,
        transaction_date TEXT NOT NULL,
        is_essential INTEGER DEFAULT 0,
        is_recurring INTEGER DEFAULT 0,
        is_income INTEGER DEFAULT 0
    );
    """)
    conn.commit()
    conn.close()


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def month_bounds(today: date):
    start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    return start, today.replace(day=last_day)


def get_user_from_token(conn, token: str):
    row = conn.execute(
        "SELECT users.* FROM sessions JOIN users ON sessions.user_id = users.id WHERE token = ?", (token,)
    ).fetchone()
    return row


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _auth_user(self, conn):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return get_user_from_token(conn, auth.removeprefix("Bearer "))

    def log_message(self, fmt, *args):
        sys.stderr.write("[devserver] " + (fmt % args) + "\n")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        conn = get_db()
        try:
            if parsed.path == "/health":
                return self._json(200, {"status": "ok", "app": "SpendShield AI (devserver)"})

            user = self._auth_user(conn)
            if not user:
                return self._json(401, {"detail": "Not authenticated"})

            if parsed.path == "/api/v1/safe-to-spend":
                return self._json(200, self._compute_safe_to_spend(conn, user))

            if parsed.path == "/api/v1/forecast":
                return self._json(200, self._compute_forecast(conn, user))

            if parsed.path == "/api/v1/analytics/velocity":
                return self._json(200, self._compute_velocity(conn, user))

            if parsed.path == "/api/v1/transactions":
                rows = conn.execute(
                    "SELECT * FROM transactions WHERE user_id = ? ORDER BY transaction_date DESC LIMIT 50",
                    (user["id"],),
                ).fetchall()
                return self._json(200, [dict(r) for r in rows])

            return self._json(404, {"detail": "Not found"})
        except Exception as e:
            return self._json(500, {"detail": str(e)})
        finally:
            conn.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        conn = get_db()
        try:
            if parsed.path == "/api/v1/auth/register":
                qs = parse_qs(parsed.query)
                email = qs.get("email", [None])[0]
                password = qs.get("password", [None])[0]
                full_name = qs.get("full_name", [""])[0]
                if not email or not password:
                    return self._json(400, {"detail": "email and password required"})
                if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                    return self._json(400, {"detail": "Email already registered"})
                salt = secrets.token_hex(16)
                conn.execute(
                    "INSERT INTO users (email, password_hash, salt, full_name) VALUES (?, ?, ?, ?)",
                    (email, hash_password(password, salt), salt, full_name),
                )
                conn.commit()
                user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
                token = secrets.token_hex(24)
                conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
                conn.commit()
                return self._json(200, {"access_token": token, "token_type": "bearer"})

            if parsed.path == "/api/v1/auth/login":
                body = self._read_body_form()
                email, password = body.get("username"), body.get("password")
                row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if not row or hash_password(password, row["salt"]) != row["password_hash"]:
                    return self._json(401, {"detail": "Incorrect email or password"})
                token = secrets.token_hex(24)
                conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row["id"]))
                conn.commit()
                return self._json(200, {"access_token": token, "token_type": "bearer"})

            user = self._auth_user(conn)
            if not user:
                return self._json(401, {"detail": "Not authenticated"})

            if parsed.path == "/api/v1/transactions":
                payload = self._read_json()
                conn.execute(
                    "INSERT INTO transactions (user_id, amount, merchant, category, "
                    "transaction_date, is_essential, is_recurring, is_income) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user["id"], payload["amount"], payload.get("merchant"), payload["category"],
                     payload["transaction_date"], int(payload.get("is_essential", False)),
                     int(payload.get("is_recurring", False)), int(payload.get("is_income", False))),
                )
                conn.commit()
                return self._json(200, {"status": "created"})

            if parsed.path == "/api/v1/budget":
                payload = self._read_json()
                today = date.today()
                conn.execute(
                    "INSERT INTO budgets (user_id, month, year, total_income, savings_target) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user["id"], today.month, today.year, payload["total_income"],
                     payload.get("savings_target", 0)),
                )
                conn.commit()
                return self._json(200, {"status": "created"})

            if parsed.path == "/api/v1/purchase/evaluate":
                payload = self._read_json()
                return self._json(200, self._compute_purchase_evaluation(conn, user, payload))

            return self._json(404, {"detail": "Not found"})
        except Exception as e:
            return self._json(500, {"detail": str(e)})
        finally:
            conn.close()

    def _read_body_form(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        from urllib.parse import parse_qsl
        return dict(parse_qsl(raw))

    def _get_current_budget(self, conn, user):
        today = date.today()
        return conn.execute(
            "SELECT * FROM budgets WHERE user_id = ? AND month = ? AND year = ? ORDER BY id DESC LIMIT 1",
            (user["id"], today.month, today.year),
        ).fetchone()

    def _compute_safe_to_spend(self, conn, user) -> dict:
        today = date.today()
        month_start, month_end = month_bounds(today)
        budget = self._get_current_budget(conn, user)
        monthly_budget = budget["total_income"] if budget else 0.0
        savings_target = budget["savings_target"] if budget else 0.0

        spent_so_far = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND is_income=0 "
            "AND transaction_date BETWEEN ? AND ?",
            (user["id"], month_start.isoformat(), today.isoformat()),
        ).fetchone()[0]

        upcoming_obligations = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND is_recurring=1 "
            "AND transaction_date < ?",
            (user["id"], month_start.isoformat()),
        ).fetchone()[0]

        essential_so_far = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND is_essential=1 "
            "AND transaction_date BETWEEN ? AND ?",
            (user["id"], month_start.isoformat(), today.isoformat()),
        ).fetchone()[0]
        elapsed_days = max((today - month_start).days, 1)
        days_remaining_incl_today = (month_end - today).days + 1
        predicted_essential = (essential_so_far / elapsed_days) * max(days_remaining_incl_today - 1, 0)

        result = calculate_safe_to_spend(SafeToSpendInput(
            monthly_budget=monthly_budget, spent_so_far=spent_so_far,
            upcoming_obligations=upcoming_obligations, predicted_essential_spend=predicted_essential,
            today=today, month_start=month_start, month_end=month_end, savings_target=savings_target,
        ))
        return result.__dict__

    def _compute_forecast(self, conn, user) -> dict:
        today = date.today()
        month_start, month_end = month_bounds(today)
        budget = self._get_current_budget(conn, user)
        monthly_budget = budget["total_income"] if budget else 0.0

        rows = conn.execute(
            "SELECT transaction_date, SUM(amount) as total FROM transactions WHERE user_id=? AND is_income=0 "
            "AND transaction_date BETWEEN ? AND ? GROUP BY transaction_date ORDER BY transaction_date",
            (user["id"], month_start.isoformat(), today.isoformat()),
        ).fetchall()
        daily_spend = [
            DailySpend(day=date.fromisoformat(r["transaction_date"]), amount=r["total"]) for r in rows
        ]
        spent_so_far = sum(d.amount for d in daily_spend)
        days_remaining = (month_end - today).days

        result = forecast_month_end_spend(
            daily_spend=daily_spend, days_remaining=days_remaining,
            monthly_budget=monthly_budget, spent_so_far=spent_so_far,
        )
        return result.__dict__

    def _compute_velocity(self, conn, user) -> dict:
        today = date.today()
        month_start, month_end = month_bounds(today)
        budget = self._get_current_budget(conn, user)
        monthly_budget = budget["total_income"] if budget else 0.0

        spent_so_far = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND is_income=0 "
            "AND transaction_date BETWEEN ? AND ?",
            (user["id"], month_start.isoformat(), today.isoformat()),
        ).fetchone()[0]

        elapsed_days = (today - month_start).days
        total_days_in_month = (month_end - month_start).days + 1
        result = calculate_spending_velocity(
            spent_so_far=spent_so_far, elapsed_days=elapsed_days,
            monthly_budget=monthly_budget, total_days_in_month=total_days_in_month,
        )
        return result.__dict__

    def _compute_purchase_evaluation(self, conn, user, payload) -> dict:
        sts = self._compute_safe_to_spend(conn, user)
        today = date.today()
        month_start, _ = month_bounds(today)

        recent_category_spend = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=? AND category=? "
            "AND transaction_date BETWEEN ? AND ?",
            (user["id"], payload["category"], month_start.isoformat(), today.isoformat()),
        ).fetchone()[0]

        same_category_7d = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id=? AND category=?",
            (user["id"], payload["category"]),
        ).fetchone()[0]

        purchase_result = evaluate_purchase(
            price=payload["price"], remaining_discretionary_budget=sts["remaining_budget"],
            days_remaining=sts["days_remaining"], recent_category_spend=recent_category_spend,
        )

        impulse = evaluate_impulse(ImpulseInput(
            amount=payload["price"], category=payload["category"], timestamp=datetime.now(),
            category_spend_this_week=recent_category_spend, category_weekly_budget=1,
            transactions_same_category_last_7d=min(same_category_7d, 10), is_recurring=False,
        ))

        intervention = decide_intervention(InterventionInput(
            impulse_score=impulse.score, budget_impact_pct=purchase_result.budget_impact_pct,
            overspend_risk=sts["overspend_risk"], remaining_budget=sts["remaining_budget"],
        ))

        return {
            "affordability_score": purchase_result.affordability_score,
            "budget_impact_pct": purchase_result.budget_impact_pct,
            "recommendation": purchase_result.recommendation,
            "reason": purchase_result.reason,
            "intervention_level": int(intervention.level),
        }


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    port = int(os.environ.get("PORT", 8787))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"SpendShield devserver running on http://0.0.0.0:{port}")
    server.serve_forever()
