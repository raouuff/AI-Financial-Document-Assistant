"""SQLite storage layer for the expense tracker (stdlib sqlite3, no ORM)."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending_review',
    doc_filename    TEXT NOT NULL,
    doc_type        TEXT,
    doc_hash        TEXT,
    doc_date        TEXT,
    vendor          TEXT,
    invoice_number  TEXT,
    description     TEXT,
    amount          REAL,
    currency        TEXT,
    tax_amount      REAL,
    category        TEXT,
    confidence      REAL,
    flags           TEXT NOT NULL DEFAULT '[]',
    raw_extraction  TEXT,
    file_path       TEXT
);
CREATE INDEX IF NOT EXISTS idx_expenses_vendor   ON expenses(vendor);
CREATE INDEX IF NOT EXISTS idx_expenses_invnum   ON expenses(invoice_number);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
"""

FIELDS = [
    "doc_filename", "doc_type", "doc_hash", "doc_date", "vendor",
    "invoice_number", "description", "amount", "currency", "tax_amount",
    "category", "confidence", "file_path",
]


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_to_dict(row) -> dict:
    d = dict(row)
    d["flags"] = json.loads(d.get("flags") or "[]")
    if d.get("raw_extraction"):
        d["raw_extraction"] = json.loads(d["raw_extraction"])
    return d


def insert_expense(data: dict, flags: list, raw: dict | None) -> dict:
    """Insert a new extracted expense and return the stored row."""
    ts = _now()
    with connect() as c:
        cur = c.execute(
            f"""INSERT INTO expenses
                (created_at, updated_at, doc_filename, doc_type, doc_hash,
                 doc_date, vendor, invoice_number, description, amount,
                 currency, tax_amount, category, confidence, flags,
                 raw_extraction, file_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts, ts, data.get("doc_filename"), data.get("doc_type"),
                data.get("doc_hash"), data.get("doc_date"), data.get("vendor"),
                data.get("invoice_number"), data.get("description"),
                data.get("amount"), data.get("currency"),
                data.get("tax_amount"), data.get("category"),
                data.get("confidence"), json.dumps(flags),
                json.dumps(raw) if raw else None, data.get("file_path"),
            ),
        )
        row = c.execute(
            "SELECT * FROM expenses WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return row_to_dict(row)


def update_expense(expense_id: int, updates: dict, flags: list | None = None) -> dict | None:
    """Update editable fields; recompute flags when requested."""
    allowed = {
        "doc_date", "vendor", "invoice_number", "description", "amount",
        "currency", "tax_amount", "category", "status",
    }
    sets, vals = [], []
    for k, v in updates.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = ?")
            vals.append(v)
    if flags is not None:
        sets.append("flags = ?")
        vals.append(json.dumps(flags))
    if not sets:
        return get_expense(expense_id)
    vals.append(_now())
    vals.append(expense_id)
    with connect() as c:
        c.execute(
            f"UPDATE expenses SET {', '.join(sets)}, updated_at = ? WHERE id = ?",
            vals,
        )
        row = c.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    return row_to_dict(row) if row else None


def get_expense(expense_id: int) -> dict | None:
    with connect() as c:
        row = c.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    return row_to_dict(row) if row else None


def list_expenses(status: str | None = None) -> list[dict]:
    q = "SELECT * FROM expenses"
    args: tuple = ()
    if status:
        q += " WHERE status = ?"
        args = (status,)
    q += " ORDER BY id DESC"
    with connect() as c:
        rows = c.execute(q, args).fetchall()
    return [row_to_dict(r) for r in rows]


def find_duplicates(candidate: dict, exclude_id: int | None = None) -> list[dict]:
    """Existing records that look like the same invoice."""
    checks, params = [], []

    if candidate.get("vendor") and candidate.get("invoice_number"):
        checks.append(
            "(LOWER(vendor) = LOWER(?) AND LOWER(invoice_number) = LOWER(?))"
        )
        params += [candidate["vendor"], candidate["invoice_number"]]

    checks.append("doc_hash = ?")
    params.append(candidate.get("doc_hash") or "")

    if (
        candidate.get("vendor") and candidate.get("amount") is not None
        and candidate.get("doc_date")
    ):
        checks.append(
            """(LOWER(vendor) = LOWER(?) AND ABS(amount - ?) < 0.005
                AND date(doc_date) BETWEEN date(?, '-3 days') AND date(?, '+3 days'))"""
        )
        params += [candidate["vendor"], candidate["amount"],
                   candidate["doc_date"], candidate["doc_date"]]

    where = " OR ".join(f"({ch})" for ch in checks)
    q = f"SELECT * FROM expenses WHERE ({where})"
    if exclude_id:
        q += " AND id != ?"
        params.append(exclude_id)
    with connect() as c:
        rows = c.execute(q, params).fetchall()
    return [
        {"id": r["id"], "doc_filename": r["doc_filename"], "vendor": r["vendor"],
         "invoice_number": r["invoice_number"], "amount": r["amount"],
         "currency": r["currency"], "doc_date": r["doc_date"]}
        for r in rows
    ]
