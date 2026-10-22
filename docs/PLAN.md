# AI-Powered Financial Management — Build Plan

## Task
Part 1: AI Financial Document Assistant — automate processing and organization of
project-related financial documents (invoices/receipts).

## Decisions (locked)
| Area | Choice | Why |
|---|---|---|
| LLM | Google Gemini 2.5 Flash | Free-tier key, strong vision PDF/image extraction, native JSON mode |
| Storage | SQLite | "equivalent" to Sheets/Airtable; zero setup; easy to demo & export |
| UI | Single FastAPI web app (one HTML page) | One command to run, easy to record demo |
| Framework | Custom Python workflow (allowed) | Simplest; no n8n/Zapier account needed |
| Demo mode | Bundled sample docs + pre-baked extractions | Testable with NO API key; real mode for actual submissions |

## Architecture
Upload (PDF/PNG/JPG) → Gemini extraction (structured JSON) → Expense
Categorization (LLM + rule-based fallback) → Validation (missing / duplicate /
inconsistent flags) → SQLite tracker → Dashboard (review/approve) → Financial
Summary (by category × currency) → CSV export.

## Milestones
1. [x] Project plan + architecture docs
2. [x] Backend: config, SQLite schema, extraction, categorization, validation, summary
3. [x] API endpoints + dashboard page
4. [x] Demo mode + sample data generator (incl. duplicate & missing-field cases)
5. [x] README (reproduction instructions), TEST_PLAN, sample outputs (CSV)
6. [x] End-to-end test run (demo mode) — verified via curl + dashboard

## Deliverables mapping
- Working prototype → `app/`, `static/`
- Source → this repo (git init with clean history)
- Sample outputs → `exports/sample_expense_tracker.csv`, `exports/sample_financial_summary.md`
- Technical doc → `docs/ARCHITECTURE.md`, `docs/TEST_PLAN.md`, `README.md`
- Reproducible demo dataset → `sample_data/` (10 fictional documents; generator in `scripts/`)
