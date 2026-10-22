"""Generate fictional sample invoices/receipts + pre-baked demo extractions.

Run:  pip install -r requirements-dev.txt && python scripts/make_samples.py

Creates in sample_data/:
  - PNG receipts / invoices (rendered text documents)
  - 1 PDF invoice
  - one *.json sidecar per sample = the pre-baked extraction used in DEMO mode

Sample coverage is deliberately designed to exercise every validation rule:
  complete invoice | no invoice number (info flag) | duplicate pair (2nd upload
  flagged) | missing date | invalid tax > total.
All data is fictional.
"""
from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE_DIR.mkdir(exist_ok=True)


# --------------------------------------------------------------------- helpers
def _font(size=22, bold=False):
    for name in (
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf"] if bold else
        ["DejaVuSans.ttf", "Arial.ttf"]
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_png(lines: list[tuple[str, int, bool]], name: str) -> Path:
    W, H = 900, 60 + 44 * len(lines)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill="#1f4e79")
    y = 30
    for text, size, bold in lines:
        d.text((50, y), text, fill="#111111", font=_font(size, bold))
        y += 44 if size >= 22 else 38
    path = SAMPLE_DIR / name
    img.save(path)
    return path


def render_pdf(header: str, lines: list[str], name: str) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 14, header, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=13)
    pdf.ln(4)
    for ln in lines:
        pdf.cell(0, 10, ln.encode("latin-1", "replace").decode("latin-1"),
                 new_x="LMARGIN", new_y="NEXT")
    path = SAMPLE_DIR / name
    pdf.output(path)
    return path


def sidecar(stem: str, data: dict) -> None:
    (SAMPLE_DIR / f"{stem}.json").write_text(
        __import__("json").dumps(data, indent=2)
    )


made = []

# 1 --- SOFTWARE subscription invoice (PDF, complete, USD) ----------------------
stem = "invoice-software-subscription-usd"
render_pdf("CLOUDPEAK SOFTWARE LTD.", [
    "Invoice No: CP-2025-00417",
    "Invoice Date: 2025-11-03",
    "Bill To: Nova Robotics Project Team",
    "Description: CloudPlan Pro — annual SaaS subscription (seats: 12)",
    "Subtotal: $1,140.00",
    "Tax / VAT (16%): $182.40",
    "Total Due: $1,322.40 USD",
    "Currency: USD",
], f"{stem}.pdf")
sidecar(stem, {
    "doc_type": "invoice", "document_date": "2025-11-03",
    "vendor": "CloudPeak Software Ltd.", "invoice_number": "CP-2025-00417",
    "description": "CloudPlan Pro annual SaaS subscription, 12 seats",
    "amount": 1322.40, "currency": "usd", "tax_amount": 182.40,
    "category": "software", "extraction_confidence": 0.97,
})
made += [f"{stem}.pdf", f"{stem}.json"]

# 2 --- OFFICE SUPPLIES receipt (PNG, no invoice number — 'missing' info flag) -
stem = "receipt-office-supplies-egp"
render_png([
    ("EL-MANSOUR STATIONERY", 26, True),
    ("Receipt #A-1187 · 12 Talaat Harb St., Cairo", 15, False),
    ("Date: 2025-11-18", 17, False),
    ("Items: printer paper (8 reams), ink toner x2, folders", 17, False),
    ("Subtotal: 293.15 EGP", 17, False),
    ("VAT (14%): 41.04 EGP", 17, False),
    ("TOTAL: 334.19 EGP", 24, True),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "receipt", "document_date": "2025-11-18",
    "vendor": "El-Mansour Stationery", "invoice_number": "",
    "description": "Printer paper, ink toner and folders",
    "amount": 334.19, "currency": "EGP", "tax_amount": 41.04,
    "category": "operational", "extraction_confidence": 0.84,
})
made += [f"{stem}.png", f"{stem}.json"]

# 3 + 4 --- TRAVEL hotel invoice, EUR — and its near-identical duplicate --------
stem = "invoice-hotel-travel-eur"
render_png([
    ("ALPENHOF BUSINESS HOTEL", 26, True),
    ("Munich, Germany", 15, False),
    ("Invoice No: ABH-449211", 17, False),
    ("Invoice Date: 2025-12-08", 17, False),
    ("Guest: Nova Robotics — Training Event", 17, False),
    ("2 rooms x 3 nights incl. breakfast", 17, False),
    ("Net: 390.00 EUR · VAT 19%: 74.10 EUR", 17, False),
    ("TOTAL: 464.10 EUR", 24, True),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "invoice", "document_date": "2025-12-08",
    "vendor": "Alpenhof Business Hotel", "invoice_number": "ABH-449211",
    "description": "2 rooms x 3 nights incl. breakfast",
    "amount": 464.10, "currency": "eur", "tax_amount": 74.10,
    "category": "travel", "extraction_confidence": 0.96,
})
made += [f"{stem}.png", f"{stem}.json"]

stem = "invoice-hotel-travel-eur-COPY"
render_png([
    ("ALPENHOF BUSINESS HOTEL", 26, True),
    ("Munich, Germany", 15, False),
    ("Invoice No: ABH-449211", 17, False),
    ("Invoice Date: 2025-12-08", 17, False),
    ("Guest: Nova Robotics — Training Event", 17, False),
    ("2 rooms x 3 nights incl. breakfast", 17, False),
    ("Net: 390.00 EUR · VAT 19%: 74.10 EUR", 17, False),
    ("TOTAL: 464.10 EUR", 24, True),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "invoice", "document_date": "2025-12-08",
    "vendor": "Alpenhof Business Hotel", "invoice_number": "ABH-449211",
    "description": "2 rooms x 3 nights incl. breakfast",
    "amount": 464.10, "currency": "eur", "tax_amount": 74.10,
    "category": "travel", "extraction_confidence": 0.96,
})
made += [f"{stem}.png", f"{stem}.json"]

# 5 --- EVENTS catering receipt with a MISSING DATE (missing-info flag) --------
stem = "receipt-event-catering-usd-nodate"
render_png([
    ("URBAN SPOON CATERING CO.", 26, True),
    ("Service: Hackathon Day 2 lunch buffet (42 guests)", 15, False),
    ("Event Date: 2025-12-14", 17, False),
    ("Payment received: 640.00 USD", 17, False),
    ("Sales tax: 57.60 USD", 17, False),
    ("TOTAL PAID: 697.60 USD", 24, True),
    ("Thank you for choosing Urban Spoon!", 15, False),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "receipt", "document_date": "",
    "vendor": "Urban Spoon Catering Co.", "invoice_number": "",
    "description": "Hackathon catering — lunch buffet, 42 guests",
    "amount": 697.60, "currency": "USD", "tax_amount": 57.60,
    "category": "events", "extraction_confidence": 0.71,
})
made += [f"{stem}.png", f"{stem}.json"]

# 6 --- EQUIPMENT invoice with inconsistent tax --------------------------------
stem = "invoice-equipment-camera-badvat"
render_png([
    ("LENSHADE PHOTO GEAR", 26, True),
    ("Invoice No: LS-88123", 17, False),
    ("Invoice Date: 2025-11-26", 17, False),
    ("Item: 4K PTZ video camera + tripod", 17, False),
    ("Unit price: 1,850.00 USD", 17, False),
    ("VAT: 2,999.00 USD", 17, False),
    ("TOTAL: 2,150.00 USD", 24, True),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "invoice", "document_date": "2025-11-26",
    "vendor": "Lenshade Photo Gear", "invoice_number": "LS-88123",
    "description": "4K PTZ video camera + tripod",
    "amount": 2150.00, "currency": "USD", "tax_amount": 2999.00,
    "category": "equipment", "extraction_confidence": 0.93,
})
made += [f"{stem}.png", f"{stem}.json"]

# 7 --- PERSONNEL contractor invoice (PDF, complete clean, USD) ----------------
stem = "invoice-personnel-contractor-usd"
render_pdf("MERIDIAN TECH CONSULTING LLC.", [
    "Invoice No: MTC-2025-1022",
    "Invoice Date: 2025-12-01",
    "Bill To: Nova Robotics Project",
    "Description: Embedded firmware contractor — 22 days x $59.50/day rate",
    "Subtotal: $1,309.00",
    "Tax / VAT (12%): $157.08",
    "Total Due: $1,466.08 USD",
    "Currency: USD",
    "Payment terms: Net 15",
], f"{stem}.pdf")
sidecar(stem, {
    "doc_type": "invoice", "document_date": "2025-12-01",
    "vendor": "Meridian Tech Consulting LLC.", "invoice_number": "MTC-2025-1022",
    "description": "Embedded firmware contractor — 22 days daily rate",
    "amount": 1466.08, "currency": "USD", "tax_amount": 157.08,
    "category": "personnel", "extraction_confidence": 0.97,
})
made += [f"{stem}.pdf", f"{stem}.json"]

# 8 --- TRAVEL taxi receipt (clean, USD) ----------------------------------------
stem = "receipt-taxi-travel-usd"
render_png([
    ("CITYRIDE TAXI SERVICE", 26, True),
    ("Ride #TX-77314 · 2025-11-30", 15, False),
    ("Airport to Project Office (14.3 km)", 15, False),
    ("Fare: 38.00 USD", 17, False),
    ("Tolls & surcharges: 4.50 USD", 17, False),
    ("TOTAL CHARGED: 42.50 USD", 24, True),
    ("Paid by corporate card", 15, False),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "receipt", "document_date": "2025-11-30",
    "vendor": "CityRide Taxi Service", "invoice_number": "TX-77314",
    "description": "Airport to project office transfer (14.3 km)",
    "amount": 42.50, "currency": "USD", "tax_amount": 4.50,
    "category": "travel", "extraction_confidence": 0.92,
})
made += [f"{stem}.png", f"{stem}.json"]

# 9 --- TRAVEL taxi receipt, same vendor + amount + date as #8, different file --
#       → exercises the vendor+amount+date(±3d) duplicate heuristic
stem = "receipt-taxi-travel-usd-same-day"
render_png([
    ("CITYRIDE TAXI SERVICE", 26, True),
    ("Ride #TX-77319 · 2025-11-30", 15, False),
    ("Project Office to Airport (14.1 km)", 15, False),
    ("Fare: 38.00 USD", 17, False),
    ("Tolls & surcharges: 4.50 USD", 17, False),
    ("TOTAL CHARGED: 42.50 USD", 24, True),
    ("Paid by corporate card", 15, False),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "receipt", "document_date": "2025-11-30",
    "vendor": "CityRide Taxi Service", "invoice_number": "TX-77319",
    "description": "Project office to airport transfer (14.1 km)",
    "amount": 42.50, "currency": "USD", "tax_amount": 4.50,
    "category": "travel", "extraction_confidence": 0.92,
})
made += [f"{stem}.png", f"{stem}.json"]

# 10 --- OPERATIONAL office rent invoice (clean, AED — 4th currency) ------------
stem = "invoice-rent-operational-aed"
render_png([
    ("EMIRATES BUSINESS CENTERS FZE", 26, True),
    ("Invoice No: EBC-2025-3345", 17, False),
    ("Invoice Date: 2025-11-01", 17, False),
    ("Shared office unit B-204, Sharjah — monthly rent, project team", 15, False),
    ("Rent: 3,040.00 AED", 17, False),
    ("Municipality fee (5%): 160.00 AED", 17, False),
    ("TOTAL DUE: 3,200.00 AED", 24, True),
], f"{stem}.png")
sidecar(stem, {
    "doc_type": "invoice", "document_date": "2025-11-01",
    "vendor": "Emirates Business Centers FZE", "invoice_number": "EBC-2025-3345",
    "description": "Shared office unit B-204 monthly rent",
    "amount": 3200.00, "currency": "AED", "tax_amount": 160.00,
    "category": "operational", "extraction_confidence": 0.95,
})
made += [f"{stem}.png", f"{stem}.json"]

print("Created in sample_data/:")
for m in made:
    print("  •", m)
