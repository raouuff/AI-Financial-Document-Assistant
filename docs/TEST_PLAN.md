# Test Plan — AI Financial Document Assistant

Two levels: **A. Quick manual E2E** (≤3 min, via the dashboard) and
**B. API/curl regression** (scriptable, matches the automated run used to
produce `exports/sample_*`).

Preconditions: app running (`python run.py`, open http://127.0.0.1:8000),
English (US) locale for date inputs.

---

## A. Quick manual E2E (dashboard)

> **Staged flow:** every upload shows an editable *staged review card* — nothing
> is stored in the tracker until you press **Confirm & add to tracker**
> (**Discard** saves nothing). Steps below assume Confirm unless stated.

| # | Step | Expected result | Pass |
|---|---|---|---|
| A1 | Open the app | Dark header shows mode badge: `DEMO MODE (no API key…)` or `LIVE MODE (Gemini)` | ☐ |
| A2 | Upload `sample_data/invoice-software-subscription-usd.pdf` | Card shows: invoice, 2025-11-03, CloudPeak Software Ltd., CP-2025-00417, USD 1322.40, VAT 182.40, category `software`, **No validation issues** | ☐ |
| A3 | Upload `receipt-office-supplies-egp.png` | Amount 334.19 EGP, category `operational`; one *info* flag "No invoice number found" | ☐ |
| A4 | Upload `invoice-hotel-travel-eur.png` then `invoice-hotel-travel-eur-COPY.png` | The COPY gets an **error** duplicate flag referencing the first record — *also note: without a first upload both are clean* | ☐ |
| A5 | Upload `receipt-event-catering-usd-nodate.png` | **error** flag `Document date is missing` | ☐ |
| A6 | In Expense Tracker, set record's date to `2025-12-14`, click **Save** | Toast "Saved & re-validated"; the missing-date flag disappears | ☐ |
| A7 | Click **Approve** on it | Badge becomes "approved"; summary includes it | ☐ |
| A8 | Click **Reject** on the duplicate copy | Badge "rejected"; it no longer counts in the summary | ☐ |
| A9 | Upload `invoice-personnel-contractor-usd.pdf` | Amount 1,466.08 USD, category `personnel`, no flags | ☐ |
| A10 | Upload `receipt-taxi-travel-usd.png`, then `receipt-taxi-travel-usd-same-day.png` | The second taxi receipt gets a **duplicate (error)** flag — although both rides are legitimate; approve both to demonstrate human judgment over the heuristic | ☐ |
| A11 | Upload `invoice-rent-operational-aed.png` | Amount 3,200.00 AED, category `operational`, no flags | ☐ |
| A12 | Financial Summary tab | KPIs + stacked bar chart by category (colored by currency); by-currency line shows `AED 3,200.00 · EGP 334.19 · EUR 464.10 · USD 5,721.08` for the decisions above (1 rejected record excluded) | ☐ |
| A13 | Export CSV / summary.md | Files download and open correctly | ☐ |

## B. API regression (curl)

```bash
BASE=http://127.0.0.1:8000
UP(){ curl -sf -F "file=@$1" $BASE/api/upload; }                                        # stage a doc
CNF(){ .venv/bin/python -c "import json,sys;print(json.load(sys.stdin)['staging_token'])"; }  # get token
CNF_TOK(){ curl -sf -X POST $BASE/api/staged/$1/confirm -H 'Content-Type: application/json' \
          -d "${2:-'{}'}"; }                                                            # confirm (+ optional edits)

# B1 health & mode
curl -s $BASE/api/health | grep -E '"status":"ok"'

# B2 staging: every upload returns a token + flags and writes NOTHING to the DB
UP sample_data/invoice-software-subscription-usd.pdf   # → flags []
curl -s $BASE/api/expenses | grep '\[\]'               # → tracker still empty ([])

# B3 confirm each staged doc (optionally with edits); repeat for all 10 samples
T1=$(UP sample_data/invoice-software-subscription-usd.pdf | CNF); CNF_TOK $T1
T2=$(UP sample_data/receipt-office-supplies-egp.png        | CNF); CNF_TOK $T2
T3=$(UP sample_data/invoice-hotel-travel-eur.png           | CNF); CNF_TOK $T3
# duplicate pair — confirm the COPY to see the duplicate flag appear on storage:
T4=$(UP sample_data/invoice-hotel-travel-eur-COPY.png      | CNF); CNF_TOK $T4   # → 1 duplicate(error) flag
T5=$(UP sample_data/receipt-event-catering-usd-nodate.png  | CNF); CNF_TOK $T5 '{"edits":{"doc_date":"2025-12-14"}}'
T6=$(UP sample_data/invoice-equipment-camera-badvat.png    | CNF); CNF_TOK $T6   # → 1 inconsistent(error) flag
T7=$(UP sample_data/invoice-personnel-contractor-usd.pdf   | CNF); CNF_TOK $T7
T8=$(UP sample_data/receipt-taxi-travel-usd.png            | CNF); CNF_TOK $T8
T9=$(UP sample_data/receipt-taxi-travel-usd-same-day.png   | CNF); CNF_TOK $T9   # → 1 duplicate(error) flag
T10=$(UP sample_data/invoice-rent-operational-aed.png       | CNF); CNF_TOK $T10

# B4 status workflow (id 4 = hotel COPY → reject; others approved)
curl -sf -X POST $BASE/api/expenses/4/status -H 'Content-Type: application/json' -d '{"status":"rejected"}'
for i in 1 2 3 5 6 7 8 9 10; do
  curl -sf -X POST $BASE/api/expenses/$i/status -H 'Content-Type: application/json' -d '{"status":"approved"}' >/dev/null
done

# B5 summary + exports (golden values: USD 5,721.08 / EUR 464.10 / EGP 334.19 /
#    AED 3,200.00 after approving all records and rejecting the hotel COPY)
curl -s $BASE/api/summary | .venv/bin/python -m json.tool
curl -s $BASE/api/export/csv
```

## C. Edge / negative tests

| # | Case | Expected | Pass |
|---|---|---|---|
| C1 | Upload `.txt` file | 415 `Unsupported file type` | ☐ |
| C2 | Upload a random PNG (not a sample) in demo mode | 422 "Demo mode only recognizes bundled sample files…" | ☐ (in real mode: extraction runs against Gemini) |
| C3 | Edit amount to `-5` and Save | record re-flagged `inconsistent: Amount is not positive` | ☐ |
| C4 | Edit date to `2030-01-01` | flag `Document date … is in the future` (warning) | ☐ |
| C5 | Edit VAT to equal amount | flag `Tax … not smaller than the total amount` | ☐ |
| C6 | Same file uploaded twice | 2nd record flagged duplicate (file hash) | ☐ |
| C7 | `GET /api/expenses?status=approved` | only approved records returned | ☐ |
| C8 | Restart the app | all records still in SQLite (persistence) | ☐ |
| C9 | Edit fields on the staged review card, then Confirm | the stored record contains the **edited** values, re-validated | ☐ |
| C10 | Press **Discard** on a staged card | tracker row count unchanged; the uploaded file is removed from `data/uploads/` | ☐ |
| C11 | Confirm a token twice / use a fake token | 404 "Staged extraction not found…" | ☐ |

## D. Real-mode (with API key) checks

| # | Case | Expected | Pass |
|---|---|---|---|
| D1 | Upload both bundled PNG samples | extraction done by Gemini; values ≈ the ground truth baked in the sidecars (± human review) | ☐ |
| D2 | Upload a genuinely new receipt photo | plausible extraction; category ∈ 6 predefined; no invented data for missing fields | ☐ |
| D3 | Blurry photo | either clean extraction or visible flags — never silent wrong values | ☐ |

## E. Deliverables checklist

- [x] Working prototype (this app)
- [x] Source code (git repo)
- [x] Sample outputs (`exports/sample_expense_tracker.csv`, `sample_financial_summary.md`, `.json`)
- [x] Technical documentation (`README.md`, `docs/ARCHITECTURE.md`, `docs/PLAN.md`)
- [x] Fictional sample documents for reproduction (`sample_data/`, 10 documents incl. a duplicate pair, a missing-date receipt, a VAT inconsistency, and a false-positive duplicate case)
