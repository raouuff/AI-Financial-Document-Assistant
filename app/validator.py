"""Data validation: missing info, inconsistent entries, duplicate invoices."""
from __future__ import annotations

import json
from datetime import date, datetime

from . import db
from .config import COMMON_CURRENCIES

FLAG_TYPES = {"missing", "duplicate", "inconsistent"}


def _parse_date(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def validate(expense: dict) -> list[dict]:
    """Run all validation rules against an expense record.

    Returns a list of flags: {type, field, message, severity, (related_id)}.
    """
    flags: list[dict] = []

    # ---------------- missing information ----------------
    required = [
        ("doc_date", "Document date"), ("vendor", "Vendor"),
        ("amount", "Amount"), ("currency", "Currency"),
        ("description", "Expense description"),
    ]
    for field, label in required:
        if expense.get(field) in (None, "", 0 if field == "amount" else None):
            flags.append({
                "type": "missing", "field": field, "severity": "error",
                "message": f"{label} is missing from the document.",
            })
    if expense.get("invoice_number") in (None, ""):
        flags.append({
            "type": "missing", "field": "invoice_number", "severity": "info",
            "message": "No invoice number found (receipts often omit it — OK if expected).",
        })

    # ---------------- inconsistent entries ----------------
    amount = expense.get("amount")
    tax = expense.get("tax_amount")
    if isinstance(amount, (int, float)) and amount <= 0:
        flags.append({
            "type": "inconsistent", "field": "amount", "severity": "error",
            "message": f"Amount is not positive ({amount}).",
        })
    if tax is not None and amount is not None and tax >= amount > 0:
        flags.append({
            "type": "inconsistent", "field": "tax_amount", "severity": "error",
            "message": f"Tax ({tax}) is not smaller than the total amount ({amount}).",
        })
    d = _parse_date(expense.get("doc_date"))
    if expense.get("doc_date") and d is None:
        flags.append({
            "type": "inconsistent", "field": "doc_date", "severity": "error",
            "message": f"Date '{expense['doc_date']}' is not a valid date format.",
        })
    elif d and d > date.today():
        flags.append({
            "type": "inconsistent", "field": "doc_date", "severity": "warning",
            "message": f"Document date {d} is in the future.",
        })
    cur = (expense.get("currency") or "").upper()
    if cur and cur not in COMMON_CURRENCIES:
        flags.append({
            "type": "inconsistent", "field": "currency", "severity": "warning",
            "message": f"Currency code '{cur}' is not a commonly recognized ISO code.",
        })
    if expense.get("category") not in (None, "") and expense.get("category") not in {
        "personnel", "travel", "equipment", "software", "events", "operational",
    }:
        flags.append({
            "type": "inconsistent", "field": "category", "severity": "warning",
            "message": f"Category '{expense['category']}' is not one of the predefined categories.",
        })

    # ---------------- duplicates (against stored records) ----------------
    exclude = expense.get("id")
    for other in db.find_duplicates(expense, exclude_id=exclude):
        reason = (
            "same file uploaded before" if other.get("same_hash")
            else f"matches record #{other['id']} ({other.get('doc_filename')})"
        )
        flags.append({
            "type": "duplicate", "field": "invoice_number", "severity": "error",
            "message": f"Potential duplicate invoice — {reason}.",
            "related_id": other["id"],
            "related_record": other,
        })

    return flags


def de_dupe(flags: list[dict]) -> list[dict]:
    """Keep only the strongest flag per (type, field) pair."""
    seen = set()
    out = []
    for f in sorted(flags, key=lambda x: {"error": 0, "warning": 1, "info": 2}[x["severity"]]):
        key = (f["type"], f["field"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def flags_json(flags: list[dict]) -> str:
    return json.dumps(flags)
