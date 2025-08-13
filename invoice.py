import os
import platform
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.units import mm

from models import Sale, SaleItem, Product, db

def format_invoice_no(n):
    return f"INV-{n:04d}"

def generate_invoice_pdf(sale_id, out_path):
    sale = Sale.query.get(sale_id)
    items = SaleItem.query.filter_by(sale_id=sale_id).all()

    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4

    # --- HEADER ---
    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 20*mm, height-40*mm, width=25*mm, height=25*mm, preserveAspectRatio=True, mask='auto')

    c.setFont('Helvetica-Bold', 16)
    c.drawString(50*mm, height-20*mm, "Patidar Traders")
    c.setFont('Helvetica', 10)
    c.drawString(50*mm, height-26*mm, "Mugaliya")
    c.drawString(50*mm, height-32*mm, "Phone: 1234567890")
    c.drawString(50*mm, height-38*mm, "GSTIN: GSTN000001")

    # Invoice info
    c.setFont('Helvetica-Bold', 12)
    c.drawRightString(width-20*mm, height-20*mm, f"Invoice #: {sale.invoice_no}")
    c.setFont('Helvetica', 10)
    c.drawRightString(width-20*mm, height-26*mm, f"Date: {sale.created_at.strftime('%Y-%m-%d')}")
    c.drawRightString(width-20*mm, height-32*mm, f"Customer: {sale.customer_name}")

    # --- TABLE ---
    data = [["Item", "Qty", "Price", "Total"]]
    for si in items:
        p = Product.query.get(si.product_id)
        name = p.name if p else str(si.product_id)
        data.append([
            name[:40],
            str(si.qty),
            f"{si.price:.2f}",
            f"{si.qty * si.price:.2f}"
        ])
    data.append(["", "", "Grand Total", f"{sale.total:.2f}"])

    table = Table(data, colWidths=[90*mm, 20*mm, 30*mm, 30*mm])
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
        ('ALIGN', (2, -1), (-1, -1), 'RIGHT'),
        ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))

    table.wrapOn(c, width, height)
    table.drawOn(c, 20*mm, height-120*mm)

    # Footer
    c.setFont('Helvetica-Oblique', 9)
    c.drawCentredString(width/2, 15*mm, "Thank you for your purchase!")

    c.save()

#     # --- AUTO-OPEN PDF ---
#     if platform.system() == "Windows":
#         os.startfile(out_path)
#     elif platform.system() == "Darwin":  # macOS
#         os.system(f"open '{out_path}'")
#     else:  # Linux and others
#         os.system(f"xdg-open '{out_path}'")
#
    return out_path



