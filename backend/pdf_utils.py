"""PDF generator for Wolf's Mind ASD receipts and balance reports."""
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image as RLImage)
import base64

PRIMARY = colors.HexColor("#1E3A5F")
LIGHT = colors.HexColor("#F5F7FA")
BORDER = colors.HexColor("#CBD5E1")
TEXT = colors.HexColor("#1F2937")


def _fmt_eur(v: float) -> str:
    s = f"{float(v or 0):,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        try:
            return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return iso


def _fmt_month(ym: str) -> str:
    months = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
              "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    try:
        y, m = ym.split("-")
        return f"{months[int(m) - 1]} {y}"
    except Exception:
        return ym


def _image_from_b64(b64: str | None, w_mm: float, h_mm: float):
    if not b64:
        return None
    try:
        from PIL import Image
        raw = b64.split(",", 1)[1] if "," in b64 else b64
        data = base64.b64decode(raw)
        # Verify image is decodable eagerly (reportlab decodes lazily)
        Image.open(BytesIO(data)).verify()
        return RLImage(BytesIO(data), width=w_mm * mm, height=h_mm * mm)
    except Exception:
        return None


def _header(org: dict, styles):
    logo = _image_from_b64(org.get("logo_base64"), 28, 28)
    right_text = f"""
        <b><font size=13 color="#1E3A5F">{org.get('name', "Wolf's Mind A.S.D.")}</font></b><br/>
        <font size=8>{org.get('address', '')}</font><br/>
        <font size=8>C.F. {org.get('fiscal_code', '')}</font><br/>
        <font size=8>Email: {org.get('email', '')}</font><br/>
        <font size=8>PEC: {org.get('pec', '')}</font><br/>
        <font size=8>{org.get('affiliation', '')}</font>
    """
    right_para = Paragraph(right_text, styles["small_right"])
    if logo:
        header_table = Table([[logo, right_para]], colWidths=[45 * mm, 130 * mm])
    else:
        left_placeholder = Paragraph(
            f"""<b><font size=14 color="#1E3A5F">{org.get('name', "Wolf's Mind A.S.D.")}</font></b><br/>
            <font size=7 color="#6B7280">ASSOCIAZIONE SPORTIVA DILETTANTISTICA</font>""",
            styles["small_left"])
        header_table = Table([[left_placeholder, right_para]], colWidths=[75 * mm, 100 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    return header_table


def _footer_text(org: dict) -> str:
    parts = [org.get("address", ""), f"C.F. {org.get('fiscal_code','')}",
             f"PEC: {org.get('pec','')}", org.get("affiliation", "")]
    return " | ".join([p for p in parts if p and p.strip() and p not in ("C.F. ", "PEC: ")])


def _make_styles():
    ss = getSampleStyleSheet()
    return {
        "small_right": ParagraphStyle("sr", parent=ss["Normal"], alignment=TA_RIGHT,
                                       fontSize=9, textColor=TEXT, leading=12),
        "small_left": ParagraphStyle("sl", parent=ss["Normal"], alignment=TA_LEFT,
                                      fontSize=9, textColor=TEXT, leading=12),
        "title": ParagraphStyle("t", parent=ss["Normal"], alignment=TA_CENTER,
                                 fontSize=22, textColor=PRIMARY,
                                 fontName="Helvetica-Bold", spaceAfter=6),
        "sect": ParagraphStyle("sect", parent=ss["Normal"], fontSize=10,
                                fontName="Helvetica-Bold", textColor=colors.white,
                                leading=14),
        "label": ParagraphStyle("lbl", parent=ss["Normal"], fontSize=8,
                                 textColor=colors.HexColor("#6B7280"),
                                 fontName="Helvetica-Bold"),
        "val": ParagraphStyle("val", parent=ss["Normal"], fontSize=10,
                               textColor=TEXT, fontName="Helvetica"),
        "note": ParagraphStyle("note", parent=ss["Normal"], fontSize=8,
                                textColor=colors.HexColor("#374151"), leading=10),
        "center_small": ParagraphStyle("cs", parent=ss["Normal"], alignment=TA_CENTER,
                                        fontSize=7, textColor=colors.HexColor("#6B7280")),
        "period": ParagraphStyle("per", parent=ss["Normal"], alignment=TA_CENTER,
                                  fontSize=11, textColor=TEXT),
    }


def _section_bar(text: str, styles):
    t = Table([[Paragraph(text, styles["sect"])]], colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _field_style():
    return TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])


def generate_receipt_pdf(receipt: dict, tesserato: dict, org: dict,
                         emesso_da_nome: str) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    st = _make_styles()
    story = [_header(org, st), Spacer(1, 8 * mm),
             Paragraph("RICEVUTA", st["title"])]

    # Numero + tessera + data row
    num_txt = f"<b>N. {receipt['numero']}</b>"
    if tesserato.get("numero_tessera"):
        num_txt += f"  <font size=9 color='#6B7280'>· Tessera n. {tesserato['numero_tessera']}</font>"
    num_row = Table([[
        Paragraph(num_txt, ParagraphStyle("n", fontSize=12, textColor=TEXT, fontName="Helvetica-Bold")),
        Paragraph(f"<b>Data:</b> {_fmt_date(receipt['data'])}",
                  ParagraphStyle("d", fontSize=11, alignment=TA_RIGHT, textColor=TEXT)),
    ]], colWidths=[110 * mm, 70 * mm])
    num_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(num_row)
    story.append(Spacer(1, 6 * mm))

    # Dati tesserato
    story.append(_section_bar("DATI DEL TESSERATO / RICEVENTE", st))
    dt = [[Paragraph("Cognome e Nome:", st["label"]),
           Paragraph(f"{tesserato.get('cognome','').upper()} {tesserato.get('nome','').upper()}", st["val"]),
           Paragraph("Codice Fiscale", st["label"]),
           Paragraph(tesserato.get("codice_fiscale", "").upper(), st["val"])]]
    t1 = Table(dt, colWidths=[30 * mm, 65 * mm, 30 * mm, 55 * mm])
    t1.setStyle(_field_style()); story.append(t1)

    addr = [[Paragraph("Indirizzo:", st["label"]),
             Paragraph(f"{tesserato.get('indirizzo','')} {tesserato.get('civico','')}", st["val"]),
             Paragraph("CAP", st["label"]),
             Paragraph(tesserato.get("cap", ""), st["val"]),
             Paragraph("Città", st["label"]),
             Paragraph(f"{tesserato.get('citta','')} ({tesserato.get('provincia','')})", st["val"])]]
    t2 = Table(addr, colWidths=[22 * mm, 55 * mm, 12 * mm, 20 * mm, 15 * mm, 56 * mm])
    t2.setStyle(_field_style()); story.append(t2)
    story.append(Spacer(1, 5 * mm))

    # Dettaglio pagamento
    story.append(_section_bar("DETTAGLIO PAGAMENTO", st))
    rows = [[Paragraph("<b>Descrizione</b>", st["val"]),
             Paragraph("<b>N. lezioni</b>",
                       ParagraphStyle("h", fontSize=10, alignment=TA_CENTER, fontName="Helvetica-Bold")),
             Paragraph("<b>Importo totale</b>",
                       ParagraphStyle("h2", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold"))]]
    for item in receipt.get("items", []):
        rows.append([Paragraph(item.get("descrizione", ""), st["val"]),
                     Paragraph(str(item.get("num_lezioni") or "-"),
                               ParagraphStyle("c", fontSize=10, alignment=TA_CENTER)),
                     Paragraph(_fmt_eur(item.get("importo", 0)),
                               ParagraphStyle("r", fontSize=10, alignment=TA_RIGHT))])
    pay = Table(rows, colWidths=[100 * mm, 30 * mm, 50 * mm])
    pay.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(pay); story.append(Spacer(1, 4 * mm))

    tot = Table([[Paragraph("Metodo di pagamento:", st["label"]),
                  Paragraph(receipt.get("metodo_pagamento", "Contanti"), st["val"]),
                  Paragraph("<b>Totale ricevuto:</b>",
                            ParagraphStyle("tl", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold")),
                  Paragraph(f"<b>{_fmt_eur(receipt.get('totale', 0))}</b>",
                            ParagraphStyle("tv", fontSize=12, alignment=TA_RIGHT,
                                            fontName="Helvetica-Bold", textColor=PRIMARY))]],
                colWidths=[45 * mm, 55 * mm, 40 * mm, 40 * mm])
    tot.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tot); story.append(Spacer(1, 5 * mm))

    if receipt.get("note"):
        story.append(Paragraph(f"<b>Note:</b> {receipt['note']}", st["val"]))
        story.append(Spacer(1, 5 * mm))

    legal = ("Operazione effettuata nell'ambito dell'attività istituzionale della ASD. "
             "I dati personali forniti sono trattati da Wolf's Mind ASD esclusivamente "
             "per finalità connesse alla gestione del rapporto associativo e in "
             "ottemperanza al Regolamento UE 2016/679 (GDPR).")
    story.append(Paragraph(legal, st["note"]))
    story.append(Spacer(1, 10 * mm))

    # Signature block
    signature = _image_from_b64(org.get("president_signature_base64"), 55, 18)
    firma_data = [[
        Paragraph(f"Emessa da: <b>{emesso_da_nome}</b>", st["val"]),
        signature if signature else Paragraph(" ", st["val"]),
    ], [
        "",
        Paragraph("Il Presidente", ParagraphStyle(
            "pr", fontSize=10, alignment=TA_CENTER, fontName="Helvetica-Bold")),
    ], [
        "",
        Paragraph(f"<i>{org.get('president_name', 'Drovelli Caivano Bruno')}</i>",
                  ParagraphStyle("pn", fontSize=10, alignment=TA_CENTER,
                                 fontName="Helvetica-Oblique")),
    ]]
    fs = Table(firma_data, colWidths=[90 * mm, 90 * mm], rowHeights=[20 * mm, 5 * mm, 5 * mm])
    fs.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LINEABOVE", (1, 1), (1, 1), 0.5, colors.black),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
    ]))
    story.append(fs)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(_footer_text(org), st["center_small"]))
    doc.build(story)
    return buf.getvalue()


def generate_balance_report_pdf(org: dict, movimenti: list, date_from: str,
                                 date_to: str, totali: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    st = _make_styles()
    story = [_header(org, st), Spacer(1, 8 * mm),
             Paragraph("REPORT BILANCIO", st["title"]),
             Spacer(1, 4 * mm),
             Paragraph(f"Periodo: <b>{_fmt_date(date_from)}</b> — <b>{_fmt_date(date_to)}</b>", st["period"]),
             Spacer(1, 8 * mm)]

    story.append(_section_bar("RIEPILOGO", st))
    riep = [[Paragraph("<b>Entrate</b>", st["val"]),
             Paragraph(_fmt_eur(totali["entrate"]),
                       ParagraphStyle("e", fontSize=12, alignment=TA_RIGHT,
                                       textColor=colors.HexColor("#059669"),
                                       fontName="Helvetica-Bold"))],
            [Paragraph("<b>Uscite</b>", st["val"]),
             Paragraph(_fmt_eur(totali["uscite"]),
                       ParagraphStyle("u", fontSize=12, alignment=TA_RIGHT,
                                       textColor=colors.HexColor("#DC2626"),
                                       fontName="Helvetica-Bold"))],
            [Paragraph("<b>Saldo</b>", ParagraphStyle("sl", fontSize=11, fontName="Helvetica-Bold")),
             Paragraph(f"<b>{_fmt_eur(totali['saldo'])}</b>",
                       ParagraphStyle("sv", fontSize=13, alignment=TA_RIGHT,
                                       fontName="Helvetica-Bold", textColor=PRIMARY))]]
    rt = Table(riep, colWidths=[130 * mm, 50 * mm])
    rt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                             ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                             ("BACKGROUND", (0, 2), (-1, 2), LIGHT)]))
    story.append(rt); story.append(Spacer(1, 6 * mm))

    # Aggregation by month
    by_month = {}
    for m in movimenti:
        ym = (m.get("data") or "")[:7]
        d = by_month.setdefault(ym, {"entrate": 0, "uscite": 0})
        if m["tipo"] == "entrata":
            d["entrate"] += m["importo"]
        else:
            d["uscite"] += m["importo"]
    if by_month:
        story.append(_section_bar("TOTALI PER MESE", st))
        mrows = [[Paragraph("<b>Mese</b>", st["val"]),
                  Paragraph("<b>Entrate</b>",
                            ParagraphStyle("mh", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold")),
                  Paragraph("<b>Uscite</b>",
                            ParagraphStyle("mh2", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold")),
                  Paragraph("<b>Saldo mese</b>",
                            ParagraphStyle("mh3", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold"))]]
        for ym in sorted(by_month.keys()):
            row = by_month[ym]
            saldo = row["entrate"] - row["uscite"]
            mrows.append([Paragraph(_fmt_month(ym), st["val"]),
                          Paragraph(_fmt_eur(row["entrate"]),
                                    ParagraphStyle("ee", fontSize=9, alignment=TA_RIGHT,
                                                    textColor=colors.HexColor("#059669"))),
                          Paragraph(_fmt_eur(row["uscite"]),
                                    ParagraphStyle("uu", fontSize=9, alignment=TA_RIGHT,
                                                    textColor=colors.HexColor("#DC2626"))),
                          Paragraph(_fmt_eur(saldo),
                                    ParagraphStyle("ss", fontSize=9, alignment=TA_RIGHT,
                                                    fontName="Helvetica-Bold"))])
        mt = Table(mrows, colWidths=[60 * mm, 40 * mm, 40 * mm, 40 * mm])
        mt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                                 ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 4),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                                 ("TOPPADDING", (0, 0), (-1, -1), 4),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.append(mt); story.append(Spacer(1, 6 * mm))

    story.append(_section_bar("DETTAGLIO MOVIMENTI", st))
    rows = [[Paragraph("<b>Data</b>", st["val"]),
             Paragraph("<b>Tipo</b>", st["val"]),
             Paragraph("<b>Categoria</b>", st["val"]),
             Paragraph("<b>Descrizione</b>", st["val"]),
             Paragraph("<b>Importo</b>",
                       ParagraphStyle("h", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold"))]]
    for m in movimenti:
        color = colors.HexColor("#059669") if m["tipo"] == "entrata" else colors.HexColor("#DC2626")
        sign = "+" if m["tipo"] == "entrata" else "-"
        rows.append([Paragraph(_fmt_date(m["data"]), st["val"]),
                     Paragraph(m["tipo"].capitalize(), st["val"]),
                     Paragraph(m.get("categoria", ""), st["val"]),
                     Paragraph((m.get("descrizione") or "")[:60], st["val"]),
                     Paragraph(f"{sign}{_fmt_eur(m['importo'])}",
                               ParagraphStyle("i", fontSize=9, alignment=TA_RIGHT, textColor=color))])
    mv = Table(rows, colWidths=[22 * mm, 20 * mm, 35 * mm, 70 * mm, 33 * mm], repeatRows=1)
    mv.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                             ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("FONTSIZE", (0, 0), (-1, -1), 9),
                             ("LEFTPADDING", (0, 0), (-1, -1), 4),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                             ("TOPPADDING", (0, 0), (-1, -1), 4),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(mv); story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(_footer_text(org), st["center_small"]))
    doc.build(story)
    return buf.getvalue()
