"""
Report exporters.

Both exporters read the report's `columns` / `rows` / `total_row`, so CSV and
PDF always agree with the on-screen preview.
"""

import csv
from decimal import Decimal
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

BRAND = colors.HexColor("#2456e6")
MUTED = colors.HexColor("#64748b")
BORDER = colors.HexColor("#e9ebf3")
HEADER_BG = colors.HexColor("#f4f5fb")


def _plain(value):
    """Render a cell value for export (no currency symbols in CSV)."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def render_csv(report):
    """Stream the report as a CSV attachment."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{report.filename}.csv"'

    writer = csv.writer(response)
    # A small provenance header — useful when these get emailed around.
    writer.writerow([report.title])
    if report.period_label:
        writer.writerow([report.period_label])
    writer.writerow([f"Generated {timezone.localtime():%Y-%m-%d %H:%M}"])
    writer.writerow([])

    writer.writerow([c["label"] for c in report.columns])
    for row in report.rows:
        writer.writerow([_plain(v) for v in row])

    total = report.total_row()
    if total:
        writer.writerow([_plain(v) for v in total])

    return response


def render_pdf(report):
    """Render the report as a PDF attachment via reportlab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=report.title,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("rwTitle", parent=styles["Heading1"],
                        fontSize=17, textColor=colors.HexColor("#0f172a"),
                        spaceAfter=2)
    sub = ParagraphStyle("rwSub", parent=styles["Normal"],
                         fontSize=9, textColor=MUTED)
    cell = ParagraphStyle("rwCell", parent=styles["Normal"], fontSize=8, leading=10)
    cell_r = ParagraphStyle("rwCellR", parent=cell, alignment=TA_RIGHT)

    story = [
        Paragraph("PropSuite", ParagraphStyle("brand", parent=styles["Normal"],
                                             fontSize=10, textColor=BRAND,
                                             spaceAfter=4)),
        Paragraph(report.title, h1),
    ]
    meta = report.period_label or ""
    story.append(Paragraph(
        f"{meta}{' · ' if meta else ''}Generated {timezone.localtime():%b %d, %Y %H:%M}", sub))
    story.append(Spacer(1, 8 * mm))

    # Summary strip
    summary = report.summary()
    if summary:
        data = [[Paragraph(f"<b>{label}</b>", cell) for label, _ in summary],
                [Paragraph(_plain(value), cell) for _, value in summary]]
        t = Table(data, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [t, Spacer(1, 6 * mm)]

    # Main table
    def styled(value, column):
        return Paragraph(_plain(value),
                         cell_r if column["align"] == "right" else cell)

    header = [Paragraph(f"<b>{c['label']}</b>", cell) for c in report.columns]
    body = [[styled(v, report.columns[i]) for i, v in enumerate(row)]
            for row in report.rows]

    if not body:
        story.append(Paragraph("No data for this period.", sub))
    else:
        total = report.total_row()
        data = [header] + body
        if total:
            data.append([styled(v, report.columns[i]) for i, v in enumerate(total)])

        table = Table(data, repeatRows=1, hAlign="LEFT")
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, len(body)), [colors.white, colors.HexColor("#fbfcfe")]),
        ]
        if total:
            style.append(("BACKGROUND", (0, -1), (-1, -1), HEADER_BG))
        table.setStyle(TableStyle(style))
        story.append(table)

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report.filename}.pdf"'
    return response
