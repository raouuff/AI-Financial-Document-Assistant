"""AI Financial Document Assistant — FastAPI application."""
from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import db, extractor, summary, validator
from .config import (
    ALLOWED_MIME, EXPORT_DIR, UPLOAD_DIR, demo_active, BASE_DIR,
)

app = FastAPI(title="AI Financial Document Assistant", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
db.init_db()


# ----------------------------------------------------------------- dashboard
@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "static" / "index.html").read_text()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mode": "demo" if demo_active() else "real",
        "today": date.today().isoformat(),
    }


# ------------------------------------------------------------------- upload
def _save_upload(file: UploadFile) -> tuple[Path, str]:
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            415, f"Unsupported file type '{mime}'. "
                 f"Allowed: {', '.join(sorted(ALLOWED_MIME))}"
        )
    data = file.file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 15 MB).")
    if not data:
        raise HTTPException(400, "Empty file.")
    dest = UPLOAD_DIR / Path(file.filename).name
    dest.write_bytes(data)
    return dest, mime


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Upload -> extract -> categorize -> validate -> store."""
    path, mime = _save_upload(file)
    try:
        extracted = extractor.extract(path, mime)
    except extractor.ExtractionError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface LLM/network issues clearly
        path.unlink(missing_ok=True)
        raise HTTPException(502, f"Extraction failed: {exc}") from exc

    record = {
        **extracted,
        "doc_filename": path.name,
        "doc_hash": extractor.file_hash(path),
        "file_path": str(path),
    }
    flags = validator.de_dupe(validator.validate(record))
    stored = db.insert_expense(record, flags, extracted)
    return stored


# ------------------------------------------------------------------ records
@app.get("/api/expenses")
def expenses(status: str | None = None):
    return db.list_expenses(status)


@app.get("/api/expenses/{expense_id}")
def get_expense(expense_id: int):
    rec = db.get_expense(expense_id)
    if not rec:
        raise HTTPException(404, "Record not found.")
    return rec


@app.patch("/api/expenses/{expense_id}")
def edit_expense(expense_id: int, updates: dict):
    """Human fixes a flagged field -> re-validate the record."""
    rec = db.get_expense(expense_id)
    if not rec:
        raise HTTPException(404, "Record not found.")
    merged = {**rec, **{k: v for k, v in updates.items() if k in validator.FLAG_TYPES or True}}
    flags = validator.de_dupe(validator.validate(merged))
    updated = db.update_expense(expense_id, updates, flags)
    if updated is None:
        raise HTTPException(404, "Record not found.")
    return updated


@app.post("/api/expenses/{expense_id}/status")
def set_status(expense_id: int, body: dict):
    status = (body.get("status") or "").strip()
    if status not in ("pending_review", "approved", "rejected"):
        raise HTTPException(400, "status must be pending_review|approved|rejected")
    updated = db.update_expense(expense_id, {"status": status})
    if updated is None:
        raise HTTPException(404, "Record not found.")
    return updated


# ------------------------------------------------------------------ summary
@app.get("/api/summary")
def financial_summary():
    return summary.build_summary()


@app.get("/api/summary.md")
@app.get("/api/summary/markdown")
def financial_summary_md():
    return PlainTextResponse(summary.to_markdown(summary.build_summary()))


# -------------------------------------------------------------------- export
@app.get("/api/export/csv", response_class=PlainTextResponse)
def export_csv():
    rows = db.list_expenses()
    buf = io.StringIO()
    cols = [
        "id", "status", "doc_type", "doc_filename", "doc_date", "vendor",
        "invoice_number", "description", "category", "amount", "currency",
        "tax_amount", "confidence", "flags",
    ]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        r = {**r, "flags": "; ".join(
            f"{f['type']}:{f['message']}" for f in r.get("flags", [])
        )}
        w.writerow(r)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition":
                                      'attachment; filename="expense_tracker.csv"'})


@app.exception_handler(HTTPException)
async def http_error(request, exc: HTTPException):  # keep responses JSON
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
