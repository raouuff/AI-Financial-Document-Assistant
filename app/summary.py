"""Financial summaries: totals by category and by currency."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from . import db


def build_summary() -> dict:
    expenses = db.list_expenses()

    total_by_category = defaultdict(float)
    total_by_currency = defaultdict(float)
    currency_by_category: dict[str, defaultdict] = defaultdict(lambda: defaultdict(float))
    open_items, flagged, duplicates = 0, 0, 0

    for e in expenses:
        if e.get("status") == "rejected":
            continue
        cat = e.get("category") or "uncategorized"
        cur = (e.get("currency") or "unknown").upper()
        amount = e.get("amount") or 0.0
        total_by_category[cat] += amount
        total_by_currency[cur] += amount
        currency_by_category[cat][cur] += amount
        if e.get("status") == "pending_review":
            open_items += 1
        errors = [f for f in e.get("flags", []) if f.get("severity") == "error"]
        if errors:
            flagged += 1
            if any(f.get("type") == "duplicate" for f in errors):
                duplicates += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_expenses": len(expenses),
        "open_items_awaiting_review": open_items,
        "items_flagged_for_review": flagged,
        "potential_duplicates": duplicates,
        "by_category": {
            cat: {
                "total_by_currency": dict(curs),
                "grand_total_for_display": " / ".join(
                    f"{c} {v:,.2f}" for c, v in sorted(curs.items())
                ),
            }
            for cat, curs in sorted(currency_by_category.items())
        },
        "by_currency": dict(sorted(total_by_currency.items())),
        "categories_used": sorted(total_by_category.keys()),
    }


def to_markdown(summary: dict) -> str:
    lines = [
        "# Project Expense Summary",
        f"_Generated: {summary['generated_at']}_",
        "",
        f"- Total expense records: **{summary['total_expenses']}**",
        f"- Awaiting review: **{summary['open_items_awaiting_review']}**",
        f"- Flagged for review: **{summary['items_flagged_for_review']}** "
        f"(potential duplicates: {summary['potential_duplicates']})",
        "",
        "## By category",
        "",
        "| Category | Total by currency |",
        "|---|---|",
    ]
    for cat, info in summary["by_category"].items():
        lines.append(f"| {cat} | {info['grand_total_for_display'] or '—'} |")
    lines += ["", "## By currency", ""]
    for cur, total in summary["by_currency"].items():
        lines.append(f"- **{cur}**: {total:,.2f}")
    return "\n".join(lines) + "\n"


def summary_json_pretty(summary: dict) -> str:
    return json.dumps(summary, indent=2)
