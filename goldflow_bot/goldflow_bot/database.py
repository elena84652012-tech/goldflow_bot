"""
GoldFlow — модуль работы с базой данных.
Хранит все операции (доходы/расходы) каждого пользователя в SQLite.
"""

import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = "goldflow.db"


@contextmanager
def get_connection():
    """Контекстный менеджер для безопасной работы с соединением."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Создаёт таблицы, если их ещё нет. Вызывается один раз при старте бота."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                is_income INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                limit_amount REAL NOT NULL,
                PRIMARY KEY (user_id, category)
            )
        """)


def add_transaction(user_id: int, amount: float, category: str, is_income: bool, note: str = ""):
    """Добавляет новую операцию (доход или расход) в базу."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transactions (user_id, amount, category, is_income, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount, category, int(is_income), note, datetime.now().isoformat())
        )


def get_transactions(user_id: int, days: int = None):
    """Возвращает список операций пользователя, опционально за последние N дней."""
    with get_connection() as conn:
        if days:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            rows = conn.execute(
                "SELECT * FROM transactions WHERE user_id = ? AND created_at >= ? ORDER BY created_at",
                (user_id, since)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at",
                (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]


def get_balance(user_id: int) -> float:
    """Считает текущий баланс: сумма доходов минус сумма расходов."""
    with get_connection() as conn:
        income = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = ? AND is_income = 1",
            (user_id,)
        ).fetchone()["total"]
        expense = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = ? AND is_income = 0",
            (user_id,)
        ).fetchone()["total"]
        return income - expense


def get_expenses_by_category(user_id: int, days: int = 30):
    """Возвращает расходы, сгруппированные по категориям (для круговой диаграммы)."""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total FROM transactions "
            "WHERE user_id = ? AND is_income = 0 AND created_at >= ? "
            "GROUP BY category ORDER BY total DESC",
            (user_id, since)
        ).fetchall()
        return {row["category"]: row["total"] for row in rows}


def get_daily_balance_trend(user_id: int, days: int = 30):
    """Возвращает баланс по дням за последние N дней (для линейного графика)."""
    since_date = datetime.now() - timedelta(days=days)
    transactions = get_transactions(user_id)

    # Считаем баланс на начало периода (все операции до since_date)
    running_balance = 0.0
    for t in transactions:
        t_date = datetime.fromisoformat(t["created_at"])
        if t_date < since_date:
            running_balance += t["amount"] if t["is_income"] else -t["amount"]

    # Строим точки по дням
    daily_totals = {}
    for t in transactions:
        t_date = datetime.fromisoformat(t["created_at"])
        if t_date >= since_date:
            day_key = t_date.date().isoformat()
            delta = t["amount"] if t["is_income"] else -t["amount"]
            daily_totals[day_key] = daily_totals.get(day_key, 0) + delta

    dates = []
    balances = []
    current_date = since_date.date()
    today = datetime.now().date()
    while current_date <= today:
        day_key = current_date.isoformat()
        running_balance += daily_totals.get(day_key, 0)
        dates.append(current_date)
        balances.append(running_balance)
        current_date += timedelta(days=1)

    return dates, balances


def set_budget(user_id: int, category: str, limit_amount: float):
    """Устанавливает лимит бюджета по категории."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, category) DO UPDATE SET limit_amount = excluded.limit_amount",
            (user_id, category, limit_amount)
        )


def get_budgets(user_id: int):
    """Возвращает все установленные лимиты бюджета пользователя."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, limit_amount FROM budgets WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return {row["category"]: row["limit_amount"] for row in rows}


def get_spent_this_month(user_id: int, category: str) -> float:
    """Считает, сколько потрачено в категории с начала текущего месяца."""
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions "
            "WHERE user_id = ? AND category = ? AND is_income = 0 AND created_at >= ?",
            (user_id, category, start_of_month.isoformat())
        ).fetchone()
        return row["total"]
