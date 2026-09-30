"""Generate 3 synthetic sample docs with known ground truth.

  invoice  : text + table
  report   : text + table + a picture containing text (OCR path)
  scan     : image-only PDF, no text layer (OCR path)

Run from the repo root:  python scripts/make_samples.py
Writes PDFs to data/pdfs and the answers to data/samples_truth.json
"""
import io
import json
from pathlib import Path

import fitz  # pymupdf
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image as RLImage, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = Path("data/pdfs")
TRUTH = Path("data/samples_truth.json")
STYLES = getSampleStyleSheet()


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def grid(rows, col_widths=None):
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    return t


def money(x):
    return f"{x:,.2f}"


def make_invoice():
    items = [("Steel bracket, 40 mm", 120, 3.75),
             ("Hydraulic hose, 2 m", 35, 18.40),
             ("Bearing set 6204", 60, 9.90),
             ("Onsite calibration (hours)", 8, 65.00)]
    subtotal = round(sum(q * p for _, q, p in items), 2)
    vat = round(subtotal * 0.14, 2)
    total = round(subtotal + vat, 2)

    rows = [["Item", "Qty", "Unit price (USD)", "Line total (USD)"]]
    rows += [[n, str(q), money(p), money(q * p)] for n, q, p in items]
    rows += [["", "", "Subtotal", money(subtotal)],
             ["", "", "VAT 14%", money(vat)],
             ["", "", "Total due", money(total)]]

    story = [
        Paragraph("INVOICE INV-2026-0417", STYLES["Title"]),
        Paragraph("Northwind Fabrication Ltd. | Issued: 12 August 2026 | "
                  "Due: 11 September 2026", STYLES["Normal"]),
        Paragraph("Bill to: Delta Cold Storage Co.", STYLES["Normal"]),
        Spacer(1, 8 * mm),
        grid(rows, [70 * mm, 20 * mm, 40 * mm, 40 * mm]),
        Spacer(1, 6 * mm),
        Paragraph("Payment terms: net 30 days. Bank transfer only.", STYLES["Normal"]),
    ]
    SimpleDocTemplate(str(OUT / "invoice_INV-2026-0417.pdf"), pagesize=A4).build(story)
    return {"file": "invoice_INV-2026-0417.pdf", "invoice_number": "INV-2026-0417",
            "subtotal": money(subtotal), "vat": money(vat), "total_due": money(total),
            "bill_to": "Delta Cold Storage Co."}


def make_report():
    months = [("June", 41200), ("July", 45800), ("August", 52300), ("September", 47100)]
    total = sum(v for _, v in months)

    # picture that contains text (goes through OCR, not the text layer)
    img = Image.new("RGB", (900, 260), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, 895, 255], outline="black", width=3)
    d.text((30, 30), "PEAK DEMAND LOG", font=font(36), fill="black")
    d.text((30, 100), "Peak demand: 4,812 kW", font=font(48), fill="black")
    d.text((30, 180), "Recorded: 14 Aug 2026 15:40", font=font(34), fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    rows = [["Month", "Consumption (kWh)"]] + [[m, f"{v:,}"] for m, v in months]
    rows.append(["Total", f"{total:,}"])

    story = [
        Paragraph("Warehouse Energy Audit, Q3 2026", STYLES["Title"]),
        Paragraph("Prepared for Delta Cold Storage Co. The audit covered the "
                  "Alexandria distribution warehouse from June to September 2026.",
                  STYLES["Normal"]),
        Spacer(1, 5 * mm),
        Paragraph("Findings", STYLES["Heading2"]),
        Paragraph("A lighting retrofit is expected to cut lighting load by 22 percent. "
                  "Refrigeration accounts for the majority of consumption.",
                  STYLES["Normal"]),
        Spacer(1, 5 * mm),
        Paragraph("Table 1. Monthly consumption", STYLES["Heading3"]),
        grid(rows, [60 * mm, 60 * mm]),
        Spacer(1, 6 * mm),
        Paragraph("Figure 1. Demand meter capture", STYLES["Heading3"]),
        RLImage(buf, width=120 * mm, height=120 * mm * 260 / 900),
    ]
    SimpleDocTemplate(str(OUT / "report_warehouse_energy_audit.pdf"), pagesize=A4).build(story)
    return {"file": "report_warehouse_energy_audit.pdf",
            "august_kwh": "52,300", "total_kwh": f"{total:,}",
            "lighting_reduction": "22 percent",
            "peak_demand_in_image": "4,812 kW", "peak_date_in_image": "14 Aug 2026"}


def make_scan():
    lines = ["HARBOR LINE SUPPLY CO.", "INTERNAL MEMO", "",
             "Ref: HL-MEMO-0093", "Date: 3 September 2026",
             "To: Procurement Committee",
             "Subject: Renewal of warehouse lease", "",
             "The lease for Unit 12 renews on 1 November 2026.",
             "Annual renewal fee: 18,250 USD.", "",
             "Approved by: R. Mostafa"]
    w, h = 1240, 1754
    page = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(page)
    y = 160
    for i, line in enumerate(lines):
        d.text((110, y), line, font=font(42 if i < 2 else 36), fill=20)
        y += 78
    page = page.rotate(1.2, resample=Image.BICUBIC, fillcolor=255)
    page = page.filter(ImageFilter.GaussianBlur(0.6))
    page = Image.blend(page, Image.effect_noise((w, h), 10), 0.05)
    jpg = io.BytesIO()
    page.save(jpg, format="JPEG", quality=70)

    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    p.insert_image(p.rect, stream=jpg.getvalue())
    doc.save(str(OUT / "scan_lease_memo.pdf"))
    doc.close()
    return {"file": "scan_lease_memo.pdf", "ref": "HL-MEMO-0093",
            "renewal_date": "1 November 2026", "renewal_fee": "18,250 USD",
            "approved_by": "R. Mostafa"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    truth = {"invoice": make_invoice(), "report": make_report(), "scan": make_scan()}
    TRUTH.write_text(json.dumps(truth, indent=2))
    print("wrote 3 PDFs to", OUT, "and", TRUTH)


if __name__ == "__main__":
    main()