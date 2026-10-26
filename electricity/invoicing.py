import io
import os
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .email_backend import invoice_email_connection
from .models import (
    ConsultationBooking,
    CustomerProfile,
    ElectricianBooking,
    Invoice,
    InvoiceLine,
    OnCallBooking,
    ServiceBooking,
)


VAT_FACTOR = Decimal("1.25")
INVOICE_LINK_SALT = "electricity.invoice-pdf"


def _sv_amount(value):
    """Format invoice numbers with Swedish separators, e.g. 2 107,20."""
    return f"{Decimal(value):,.2f}".replace(",", " ").replace(".", ",")


def _invoice_category_totals(invoice):
    """Return category totals after row and invoice discounts, split by VAT."""
    lines = list(invoice.lines.all())
    base_after_row_discounts = sum(
        (line.total_ex_vat - line.discount_amount for line in lines),
        Decimal("0"),
    )
    invoice_discount = max(invoice.discount_total - sum(
        (line.discount_amount for line in lines), Decimal("0")
    ), Decimal("0"))
    ratio = (
        (base_after_row_discounts - invoice_discount) / base_after_row_discounts
        if base_after_row_discounts else Decimal("1")
    )
    totals = {
        category: {"ex_vat": Decimal("0"), "vat": Decimal("0"), "inc_vat": Decimal("0")}
        for category in InvoiceLine.Category.values
    }
    for line in lines:
        ex_vat = (line.total_ex_vat - line.discount_amount) * ratio
        vat = ex_vat * line.vat_percent / Decimal("100")
        totals[line.category]["ex_vat"] += ex_vat
        totals[line.category]["vat"] += vat
        totals[line.category]["inc_vat"] += ex_vat + vat
    q = Decimal("0.01")
    for category in totals.values():
        for key, value in category.items():
            category[key] = value.quantize(q)
    return totals


def _value(booking, *names, default=""):
    for name in names:
        value = getattr(booking, name, None)
        if value not in (None, ""):
            return value
    return default


def customer_for_booking(booking):
    email = _value(booking, "email")
    customer = CustomerProfile.objects.filter(email__iexact=email).first() if email else None
    if customer:
        booking_values = {
            "phone": _value(booking, "phone"),
            "street_address": _value(booking, "street_address", "company_address", "site_address"),
            "postal_code": _value(booking, "postal_code", "postcode", "zip_code"),
            "city": _value(booking, "city"),
            "company_name": _value(booking, "organization_name", "company_name"),
            "organization_number": _value(booking, "organization_number"),
        }
        changed_fields = []
        for field, value in booking_values.items():
            if value and not getattr(customer, field, ""):
                setattr(customer, field, value)
                changed_fields.append(field)
        if changed_fields:
            customer.save(update_fields=[*changed_fields])
        return customer
    is_business = bool(_value(booking, "organization_number", "organization_name", "company_name"))
    name = _value(booking, "organization_name", "company_name", "full_name", "contact_person", default="Customer")
    return CustomerProfile.objects.create(
        account_type=CustomerProfile.AccountType.BUSINESS if is_business else CustomerProfile.AccountType.PRIVATE,
        full_name=name,
        email=email,
        phone=_value(booking, "phone"),
        street_address=_value(booking, "street_address", "company_address", "site_address"),
        city=_value(booking, "city"),
        postal_code=_value(booking, "postal_code", "postcode", "zip_code"),
        personal_id=_value(booking, "personal_id"),
        company_name=_value(booking, "organization_name", "company_name"),
        organization_number=_value(booking, "organization_number"),
        property_designation=_value(booking, "brf_name"),
    )


def _add_line(invoice, category, description, gross_amount, rot=False, quantity=1, unit="fixed price"):
    gross = Decimal(str(gross_amount or 0))
    if gross <= 0:
        return
    InvoiceLine.objects.create(
        invoice=invoice,
        category=category,
        description=description,
        quantity=Decimal(str(quantity)),
        unit=unit,
        unit_price_ex_vat=(gross / VAT_FACTOR / Decimal(str(quantity))).quantize(Decimal("0.01")),
        vat_percent=Decimal("25"),
        rot_eligible=rot and category == InvoiceLine.Category.LABOUR,
    )


@transaction.atomic
def create_invoice_for_booking(booking):
    relation = {
        ConsultationBooking: "consultation_booking",
        ServiceBooking: "service_booking",
        ElectricianBooking: "electrician_booking",
        OnCallBooking: "on_call_booking",
    }.get(type(booking))
    if not relation:
        raise ValueError("Unsupported booking type")
    existing = Invoice.objects.filter(**{relation: booking}).first()
    if existing:
        return existing

    customer = customer_for_booking(booking)
    rot_enabled = bool(_value(booking, "rot_deduction", "rot_requested", default=False))
    invoice = Invoice.objects.create(
        customer=customer,
        recipient_email=customer.email,
        title="Faktura",
        invoice_type=Invoice.InvoiceType.ROT if rot_enabled else Invoice.InvoiceType.STANDARD,
        status=Invoice.Status.READY,
        reference=f"BOOKING-{booking.pk}",
        work_address=", ".join(filter(None, [
            str(_value(booking, "street_address", "company_address", "site_address")),
            str(_value(booking, "zip_code")),
            str(_value(booking, "city")),
        ])),
        currency=_value(booking, "currency", default="SEK"),
        rot_enabled=rot_enabled,
        rot_percent=Decimal(str(_value(booking, "rot_percent_snapshot", default=30) or 30)),
        rot_personal_number=_value(booking, "personal_id"),
        rot_property_designation=_value(booking, "brf_name", default=customer.property_designation),
        rot_apartment_number=_value(booking, "apartment_number"),
        **{relation: booking},
    )

    if isinstance(booking, ElectricianBooking):
        multiplier = 2 if booking.arrival_window in {
            "Evening (05:00 PM - 10:00 PM)", "Night (10:00 PM - 06:00 AM)"
        } else 1
        labour = Decimal(str(booking.hourly_rate_snapshot or 0)) * booking.hours * multiplier
        _add_line(invoice, InvoiceLine.Category.LABOUR, booking.work_description or "Electrical labour", labour, rot_enabled, booking.hours, "hours")
        _add_line(invoice, InvoiceLine.Category.TRANSPORT, "Transport fee", booking.transport_fee_snapshot)
    elif isinstance(booking, ServiceBooking):
        labour = Decimal(str(booking.hourly_rate_snapshot or 0)) * max(booking.hourly_hours, 1)
        service_total = Decimal(str(booking.fixed_services_total or booking.service_fee_total or 0))
        _add_line(invoice, InvoiceLine.Category.LABOUR, booking.work_description or "Electrical service", labour or service_total, rot_enabled, max(booking.hourly_hours, 1), "hours" if labour else "fixed price")
        _add_line(invoice, InvoiceLine.Category.MATERIAL, "Selected fixed services", service_total if labour else 0)
        _add_line(invoice, InvoiceLine.Category.TRANSPORT, "Transport fee", booking.transport_fee)
    elif isinstance(booking, OnCallBooking):
        _add_line(invoice, InvoiceLine.Category.LABOUR, booking.recurring_issues or booking.service_plan, booking.estimated_total, False, booking.emergency_hours, "hours")
    else:
        _add_line(invoice, InvoiceLine.Category.LABOUR, booking.project_description or "Electrical consultation", booking.consultation_price, False)

    if not invoice.lines.exists():
        InvoiceLine.objects.create(
            invoice=invoice,
            category=InvoiceLine.Category.OTHER,
            description="Booking – price to be confirmed",
            quantity=1,
            unit="fixed price",
            unit_price_ex_vat=0,
            vat_percent=25,
        )
    invoice.recalculate()
    return invoice


def invoice_pdf_bytes(invoice):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import CondPageBreak, Flowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#09255B")
    gold = colors.HexColor("#D5AC3E")
    ink = colors.HexColor("#202735")
    muted_navy = colors.HexColor("#43536B")
    story = []
    title = invoice.title or "Faktura"
    title_block = Table(
        [[Paragraph(
            f"<para alignment='center'><font color='#09255B'><b>{title.upper()} {invoice.invoice_number}</b></font></para>",
            styles["Title"],
        )]],
        colWidths=[68 * mm],
        hAlign="CENTER",
    )
    title_block.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.8, gold),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(title_block)
    if invoice.invoice_type == Invoice.InvoiceType.PART and invoice.part_number and invoice.part_total:
        story.append(Paragraph(
            f"<para alignment='center'>DEL {invoice.part_number} AV {invoice.part_total}</para>",
            styles["Normal"],
        ))
    story.append(Spacer(1, 8 * mm))

    logo_path = settings.BASE_DIR / "electricity" / "static" / "electricity" / "img" / "electricity_logo.jpg"
    company = [
        Paragraph("<b>FÖRETAGSINFORMATION</b><br/><br/><b>RWM Helservice AB</b><br/>Faktura@rwmel.se<br/><br/>Org.nr&nbsp;&nbsp;559545-1351<br/>Bankgiro&nbsp;&nbsp;5192-1302<br/>Kontonummer&nbsp;&nbsp;6184-556026438", styles["BodyText"])
    ]
    if logo_path.exists():
        company.insert(0, Image(str(logo_path), width=28 * mm, height=28 * mm))
    customer = invoice.customer

    class CustomerInformationCard(Flowable):
        def __init__(self):
            super().__init__()
            self.width = 88 * mm
            self.height = 70 * mm

        def wrap(self, available_width, available_height):
            return min(self.width, available_width), self.height

        def draw(self):
            pdf = self.canv
            width, height = self.width, self.height
            padding = 5 * mm
            amount_currency = "kr" if invoice.currency.upper() == "SEK" else invoice.currency
            amount = f"{invoice.invoice_total:,.2f}".replace(",", " ").replace(".", ",")
            amount_label = "Fakturabelopp" if invoice.status == Invoice.Status.PAID else "Summa att betala"
            billing_address = (
                customer.company_address
                if customer.account_type == CustomerProfile.AccountType.BUSINESS and customer.company_address
                else customer.street_address
            )

            pdf.setStrokeColor(navy)
            pdf.setLineWidth(1.2)
            pdf.roundRect(0, 0, width, height, 2.2 * mm, stroke=1, fill=0)

            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold", 7.5)
            pdf.drawString(padding, height - 7 * mm, "KUNDINFORMATION")
            pdf.setStrokeColor(gold)
            pdf.setLineWidth(1.2)
            pdf.line(padding, height - 9 * mm, padding + 39 * mm, height - 9 * mm)

            customer_rows = [
                ("Kundnummer", customer.customer_number or "-"),
                ("Kundnamn", customer.full_name or "-"),
                ("Telefonnummer", customer.phone or "-"),
                ("Fakturaadress", billing_address or "-"),
                ("Postnummer och ort", " ".join(filter(None, [customer.postal_code, customer.city])) or "-"),
            ]
            row_y = height - 15 * mm
            for label, value in customer_rows:
                pdf.setFillColor(muted_navy)
                pdf.setFont("Helvetica", 7.2)
                pdf.drawString(padding, row_y, label)
                pdf.setFillColor(ink)
                pdf.setFont("Helvetica", 7.2)
                pdf.drawRightString(width - padding, row_y, str(value))
                row_y -= 4.6 * mm

            divider_y = row_y + 1.6 * mm
            pdf.setStrokeColor(colors.HexColor("#9AA7BD"))
            pdf.setLineWidth(.65)
            pdf.line(0, divider_y, width, divider_y)

            payment_rows = [
                ("Förfallodatum", invoice.due_date.isoformat(), "Helvetica", 7.2),
                (amount_label, f"{amount} {amount_currency}", "Helvetica-Bold", 11),
                ("Fakturanummer", str(invoice.invoice_number), "Helvetica", 7.2),
                ("Bankgiro", "5192-1302", "Helvetica", 7.2),
            ]
            row_y = divider_y - 5.5 * mm
            for label, value, font, size in payment_rows:
                pdf.setFillColor(muted_navy)
                pdf.setFont("Helvetica", 7.2)
                pdf.drawString(padding, row_y, label)
                pdf.setFillColor(navy if font == "Helvetica-Bold" else ink)
                pdf.setFont(font, size)
                pdf.drawRightString(width - padding, row_y, value)
                row_y -= 5 * mm

    customer_box = CustomerInformationCard()
    info = Table([[company, customer_box]], colWidths=[88 * mm, 88 * mm])
    info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([info, Spacer(1, 7 * mm)])

    meta = Table([
        ["Fakturanummer", invoice.invoice_number, "Fakturadatum", invoice.invoice_date],
        ["Kundnummer", customer.customer_number, "Betalningsvillkor", f"{invoice.payment_terms_days} dagar"],
        ["Er referens", invoice.reference or "-", "Dröjsmålsränta", "12%"],
    ], colWidths=[35 * mm, 48 * mm, 35 * mm, 48 * mm])
    meta.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, navy),
        ("LINEBELOW", (0, -1), (-1, -1), 1, navy),
        ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("TEXTCOLOR", (0, 0), (0, -1), muted_navy),
        ("TEXTCOLOR", (2, 0), (2, -1), muted_navy),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([meta, Spacer(1, 9 * mm)])

    rows = [["Beskrivning", "Moms", "Antal", "À-pris", "Summa"]]
    for line in invoice.lines.all():
        rows.append([
            Paragraph(line.description.replace("\n", "<br/>"), styles["BodyText"]),
            f"{line.vat_percent:.2f}%",
            f"{line.quantity:.2f}",
            _sv_amount(line.unit_price_ex_vat),
            _sv_amount(line.total_inc_vat),
        ])
    table = Table(rows, colWidths=[82 * mm, 20 * mm, 18 * mm, 30 * mm, 30 * mm])
    table.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, navy), ("LINEBELOW", (0, 0), (-1, 0), 1, navy), ("LINEBELOW", (0, -1), (-1, -1), .5, colors.lightgrey), ("TEXTCOLOR", (0, 0), (-1, -1), ink), ("TEXTCOLOR", (0, 0), (-1, 0), navy), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("PADDING", (0, 0), (-1, -1), 5)]))
    story.extend([table, Spacer(1, 4 * mm)])

    category_totals = _invoice_category_totals(invoice)
    labour = category_totals[InvoiceLine.Category.LABOUR]
    material = category_totals[InvoiceLine.Category.MATERIAL]
    transport = category_totals[InvoiceLine.Category.TRANSPORT]
    other = category_totals[InvoiceLine.Category.OTHER]
    display_currency = "kr" if invoice.currency.upper() == "SEK" else invoice.currency
    summary_rows = [
        ["Arbete exkl. moms", f"{_sv_amount(labour['ex_vat'])} {display_currency}"],
        ["Material exkl. moms", f"{_sv_amount(material['ex_vat'])} {display_currency}"],
    ]
    if transport["ex_vat"]:
        summary_rows.append(["Transport exkl. moms", f"{_sv_amount(transport['ex_vat'])} {display_currency}"])
    if other["ex_vat"]:
        summary_rows.append(["Övrigt exkl. moms", f"{_sv_amount(other['ex_vat'])} {display_currency}"])
    ex_vat_total_row = len(summary_rows)
    summary_rows.extend([
        ["Summa exkl. moms", f"{_sv_amount(invoice.total_inc_vat - invoice.vat_total)} {display_currency}"],
        ["Moms 25 % på arbete", f"{_sv_amount(labour['vat'])} {display_currency}"],
        ["Moms 25 % på material", f"{_sv_amount(material['vat'])} {display_currency}"],
    ])
    if transport["vat"]:
        summary_rows.append(["Moms 25 % på transport", f"{_sv_amount(transport['vat'])} {display_currency}"])
    if other["vat"]:
        summary_rows.append(["Moms 25 % på övrigt", f"{_sv_amount(other['vat'])} {display_currency}"])
    vat_total_row = len(summary_rows)
    summary_rows.extend([
        ["Moms 25 %", f"{_sv_amount(invoice.vat_total)} {display_currency}"],
        ["Summa inkl. moms", f"{_sv_amount(invoice.total_inc_vat)} {display_currency}"],
    ])
    if invoice.discount_total:
        summary_rows.insert(ex_vat_total_row, ["Rabatt", f"-{_sv_amount(invoice.discount_total)} {display_currency}"])
        ex_vat_total_row += 1
        vat_total_row += 1
    total_inc_vat_row = vat_total_row + 1
    if invoice.rot_enabled or invoice.rot_total:
        rot_prefix = "-" if invoice.rot_total else ""
        summary_rows.append([f"ROT-avdrag {invoice.rot_percent:g} % (på arbetskostnad)", f"{rot_prefix}{_sv_amount(invoice.rot_total)} {display_currency}"])
    amount_due_row = len(summary_rows)
    total_label = "FAKTURABELOPP" if invoice.status == Invoice.Status.PAID else "SUMMA ATT BETALA"
    summary_rows.append([total_label, f"{_sv_amount(invoice.invoice_total)} {display_currency}"])
    summary = Table(summary_rows, colWidths=[72 * mm, 36 * mm])
    summary.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("TEXTCOLOR", (0, 0), (0, -1), muted_navy),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1.1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
        ("LINEABOVE", (0, ex_vat_total_row), (-1, ex_vat_total_row), .7, colors.HexColor("#8CA4C4")),
        ("LINEABOVE", (0, vat_total_row), (-1, vat_total_row), .7, colors.HexColor("#8CA4C4")),
        ("LINEABOVE", (0, total_inc_vat_row), (-1, total_inc_vat_row), .7, colors.HexColor("#8CA4C4")),
        ("FONTNAME", (0, ex_vat_total_row), (-1, ex_vat_total_row), "Helvetica-Bold"),
        ("FONTNAME", (0, vat_total_row), (-1, vat_total_row), "Helvetica-Bold"),
        ("FONTNAME", (0, total_inc_vat_row), (-1, total_inc_vat_row), "Helvetica-Bold"),
        ("BOX", (0, amount_due_row), (-1, amount_due_row), 1.2, gold),
        ("TEXTCOLOR", (0, amount_due_row), (-1, amount_due_row), navy),
        ("FONTNAME", (0, amount_due_row), (-1, amount_due_row), "Helvetica-Bold"),
        ("FONTSIZE", (0, amount_due_row), (0, amount_due_row), 8.5),
        ("FONTSIZE", (1, amount_due_row), (1, amount_due_row), 13),
        ("TOPPADDING", (0, amount_due_row), (-1, amount_due_row), 3.5),
        ("BOTTOMPADDING", (0, amount_due_row), (-1, amount_due_row), 3.5),
    ]))

    rot_information = None
    if invoice.rot_enabled:
        rot_information = Table(
            [
                ["UPPGIFTER FÖR ROT-AVDRAG", ""],
                ["Personnummer:", "Fastighetsbeteckning:"],
                [invoice.rot_personal_number, invoice.rot_property_designation],
            ],
            colWidths=[43 * mm, 43 * mm],
        )
        rot_information.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, -1), navy),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (1, 0), 1, navy),
            ("LINEBELOW", (0, 2), (0, 2), .6, colors.HexColor("#9AA7BD")),
            ("LINEBELOW", (1, 2), (1, 2), .6, colors.HexColor("#9AA7BD")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))

    def draw_invoice_footer(pdf, _document):
        page_width, _ = A4
        left = 12 * mm
        right = page_width - 12 * mm
        top = 38 * mm
        navy_value = colors.HexColor("#09255B")

        pdf.saveState()
        pdf.setStrokeColor(navy_value)
        pdf.setLineWidth(1)
        pdf.line(left, top, right, top)

        # Highlighted amount-due bar immediately above the footer.
        total_bottom = top + 2 * mm
        total_height = 8 * mm
        total_currency = "kr" if invoice.currency.upper() == "SEK" else invoice.currency
        total_value = f"{invoice.invoice_total:,.2f}".replace(",", " ").replace(".", ",")
        total_label = "FAKTURABELOPP" if invoice.status == Invoice.Status.PAID else "SUMMA ATT BETALA"
        pdf.setStrokeColor(colors.HexColor("#D5AC3E"))
        pdf.setLineWidth(1.2)
        pdf.rect(left, total_bottom, right - left, total_height)
        pdf.setFillColor(navy_value)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(left + 3 * mm, total_bottom + 2.5 * mm, total_label)
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(right - 3 * mm, total_bottom + 2 * mm, f"{total_value} {total_currency}")

        # Signature and company address.
        pdf.setFillColor(navy_value)
        pdf.setFont("Helvetica-Oblique", 20)
        pdf.drawString(left + 2 * mm, top - 9 * mm, "RwmEl")
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(left + 2 * mm, top - 15 * mm, "RWM Helservice AB")
        pdf.setFont("Helvetica", 6.5)
        pdf.drawString(left + 2 * mm, top - 19 * mm, "Kikarvägen 18")
        pdf.drawString(left + 2 * mm, top - 23 * mm, "175 46 JÄRFÄLLA")

        first_divider = left + 48 * mm
        second_divider = left + 112 * mm
        pdf.line(first_divider, top - 3 * mm, first_divider, top - 27 * mm)
        pdf.line(second_divider, top - 3 * mm, second_divider, top - 27 * mm)

        # Payment information.
        payment_x = first_divider + 5 * mm
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(payment_x, top - 7 * mm, "BETALNINGSINFORMATION")
        pdf.setFont("Helvetica", 6.5)
        footer_rows = [
            ("Referens", str(invoice.invoice_number)),
            ("Bankgiro", "5192-1302"),
            ("Kontonummer", "6184-556026438"),
        ]
        footer_y = top - 13 * mm
        for label, value in footer_rows:
            pdf.drawString(payment_x, footer_y, label)
            pdf.drawString(payment_x + 25 * mm, footer_y, value)
            footer_y -= 5 * mm

        # Thank-you block.
        icon_x = second_divider + 10 * mm
        icon_y = top - 15 * mm
        pdf.setStrokeColor(navy_value)
        pdf.setLineWidth(1.2)
        pdf.circle(icon_x, icon_y, 7 * mm, stroke=1, fill=0)
        # Small bank/building symbol, kept vector so it remains sharp in PDF.
        pdf.line(icon_x - 4 * mm, icon_y + 2 * mm, icon_x, icon_y + 5 * mm)
        pdf.line(icon_x, icon_y + 5 * mm, icon_x + 4 * mm, icon_y + 2 * mm)
        pdf.line(icon_x - 4 * mm, icon_y + 2 * mm, icon_x + 4 * mm, icon_y + 2 * mm)
        for pillar_x in (-2.5, 0, 2.5):
            pdf.line(icon_x + pillar_x * mm, icon_y + 1.5 * mm, icon_x + pillar_x * mm, icon_y - 3 * mm)
        pdf.line(icon_x - 4 * mm, icon_y - 3.5 * mm, icon_x + 4 * mm, icon_y - 3.5 * mm)

        thanks_x = second_divider + 21 * mm
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(thanks_x, top - 8 * mm, "Tack för ditt förtroende!")
        pdf.setFont("Helvetica", 6.5)
        pdf.drawString(thanks_x, top - 13 * mm, "Betala gärna i tid.")
        pdf.drawString(thanks_x, top - 18 * mm, "Vid frågor, kontakta oss")
        pdf.drawString(thanks_x, top - 23 * mm, "på Faktura@rwmel.se.")
        pdf.restoreState()

    # Keep the total and footer in the normal document flow. This removes the
    # large empty area on short invoices while still moving them down naturally
    # when an invoice contains more product rows.
    display_currency = "kr" if invoice.currency.upper() == "SEK" else invoice.currency
    display_total = f"{invoice.invoice_total:,.2f}".replace(",", " ").replace(".", ",")
    display_total_label = "FAKTURABELOPP" if invoice.status == Invoice.Status.PAID else "SUMMA ATT BETALA"
    total_bar = Table(
        [[display_total_label, f"{display_total} {display_currency}"]],
        # Keep the total bar on the same 180 mm grid as the line-items table.
        colWidths=[120 * mm, 60 * mm],
    )
    total_bar.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, gold),
        ("TEXTCOLOR", (0, 0), (-1, -1), navy),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, 0), 8),
        ("FONTSIZE", (1, 0), (1, 0), 13),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    footer_text_style = styles["BodyText"].clone("InvoiceFooterText")
    footer_text_style.fontName = "Helvetica"
    footer_text_style.fontSize = 6.5
    footer_text_style.leading = 9
    footer_text_style.textColor = navy
    footer_text_style.alignment = 1
    signature_font = "Helvetica-Oblique"
    signature_font_path = r"C:\Windows\Fonts\segoesc.ttf"
    if os.path.exists(signature_font_path):
        if "InvoiceSignature" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("InvoiceSignature", signature_font_path))
        signature_font = "InvoiceSignature"

    payment_qr_path = os.path.join(
        os.path.dirname(__file__),
        "static",
        "electricity",
        "img",
        "invoice-payment-qr.jpg",
    )

    class InvoiceFooterBlock(Flowable):
        def __init__(self):
            super().__init__()
            self.width = 186 * mm
            self.height = 33 * mm

        def wrap(self, available_width, available_height):
            return min(self.width, available_width), self.height

        def draw(self):
            pdf = self.canv
            width, height = self.width, self.height
            footer_top = height
            first_divider = 48 * mm
            second_divider = 116 * mm
            third_divider = 145 * mm

            # Footer structure.
            pdf.setStrokeColor(navy)
            pdf.setLineWidth(.8)
            pdf.line(0, footer_top, width, footer_top)
            pdf.line(first_divider, footer_top - 2 * mm, first_divider, 1 * mm)
            pdf.line(second_divider, footer_top - 2 * mm, second_divider, 1 * mm)
            pdf.line(third_divider, footer_top - 2 * mm, third_divider, 1 * mm)

            # Signature section; positions are fixed so the script cannot
            # collide with the company address.
            section_one_center = first_divider / 2
            pdf.setFillColor(navy)
            pdf.setFont(signature_font, 17)
            pdf.drawCentredString(section_one_center, footer_top - 9 * mm, "RwmEl")
            pdf.setStrokeColor(gold)
            pdf.setLineWidth(1.1)
            pdf.line(section_one_center - 15 * mm, footer_top - 11 * mm, section_one_center + 15 * mm, footer_top - 11 * mm)
            pdf.setFillColor(ink)
            pdf.setFont("Helvetica-Bold", 6.2)
            pdf.drawCentredString(section_one_center, footer_top - 17 * mm, "RWM Helservice AB")
            pdf.setFont("Helvetica", 6.2)
            pdf.drawCentredString(section_one_center, footer_top - 21.5 * mm, "Kikarvägen 18")
            pdf.drawCentredString(section_one_center, footer_top - 26 * mm, "175 46 JÄRFÄLLA")

            # Payment section.
            section_two_center = (first_divider + second_divider) / 2
            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold", 6.2)
            pdf.drawCentredString(section_two_center, footer_top - 7 * mm, "BETALNINGSINFORMATION")
            payment_rows = [
                ("Referens", str(invoice.invoice_number)),
                ("Bankgiro", "5192-1302"),
                ("Kontonummer", "6184-556026438"),
            ]
            payment_y = footer_top - 14 * mm
            pdf.setFillColor(ink)
            pdf.setFont("Helvetica", 6.1)
            for label, value in payment_rows:
                pdf.drawString(first_divider + 9 * mm, payment_y, label)
                pdf.drawRightString(second_divider - 8 * mm, payment_y, value)
                payment_y -= 5 * mm

            # Payment QR supplied by the client. Keep it square and large
            # enough to scan from both the dashboard preview and emailed PDF.
            qr_size = 20 * mm
            qr_x = second_divider + ((third_divider - second_divider) - qr_size) / 2
            qr_y = footer_top - 22 * mm
            if os.path.exists(payment_qr_path):
                pdf.drawImage(
                    payment_qr_path,
                    qr_x,
                    qr_y,
                    width=qr_size,
                    height=qr_size,
                    preserveAspectRatio=True,
                )
            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold", 5.2)
            qr_center = (second_divider + third_divider) / 2
            pdf.drawCentredString(qr_center, footer_top - 25 * mm, "Skanna för")
            pdf.drawCentredString(qr_center, footer_top - 28 * mm, "betalningsuppgifter")

            thanks_x = third_divider + 5 * mm
            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold", 6)
            pdf.drawString(thanks_x, footer_top - 10 * mm, "Tack för ditt förtroende!")
            pdf.setFillColor(ink)
            pdf.setFont("Helvetica", 5.8)
            pdf.drawString(thanks_x, footer_top - 15 * mm, "Betala gärna i tid.")
            pdf.drawString(thanks_x, footer_top - 20 * mm, "Vid frågor, kontakta oss")
            pdf.drawString(thanks_x, footer_top - 25 * mm, "på Faktura@rwmel.se.")
    signature_mark = Table(
        [[Paragraph(f"<font name='{signature_font}' size='18'>RwmEl</font>", footer_text_style)]],
        colWidths=[30 * mm],
    )
    signature_mark.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, gold),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    signature_address = Paragraph(
        "<b>RWM Helservice AB</b><br/>Kikarvägen 18<br/>175 46 JÄRFÄLLA",
        footer_text_style,
    )
    signature = Table(
        [[signature_mark], [signature_address]],
        colWidths=[54 * mm],
    )
    signature.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    payment = Paragraph(
        "<b>BETALNINGSINFORMATION</b><br/><br/>"
        f"Referens&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{invoice.invoice_number}<br/>"
        "Bankgiro&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;5192-1302<br/>"
        "Kontonummer&nbsp;&nbsp;6184-556026438",
        footer_text_style,
    )
    thanks = Table(
        [[Paragraph("<font size='20'>◎</font>", footer_text_style), Paragraph(
            "<b>Tack för ditt förtroende!</b><br/>Betala gärna i tid.<br/>"
            "Vid frågor, kontakta oss<br/>på Faktura@rwmel.se.",
            footer_text_style,
        )]],
        colWidths=[12 * mm, 42 * mm],
    )
    thanks.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    footer = Table(
        [[signature, payment, thanks]],
        colWidths=[62 * mm, 62 * mm, 62 * mm],
        rowHeights=[31 * mm],
    )
    footer.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, navy),
        ("LINEAFTER", (0, 0), (1, 0), .8, navy),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    summary_block = Table(
        [[rot_information or "", summary]],
        # ``summary`` is 108 mm wide. The previous 93 mm second cell made it
        # overflow its parent table and appear too far to the right.
        colWidths=[72 * mm, 108 * mm],
        hAlign="LEFT",
    )
    summary_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    # Keep the financial breakdown close to the item table, matching the
    # approved reference instead of forcing it to the bottom of a sparse page.
    story.extend([
        CondPageBreak(88 * mm),
        summary_block,
        Spacer(1, 3 * mm),
        InvoiceFooterBlock(),
    ])
    doc.build(story)
    return buffer.getvalue()


def invoice_pdf_token(invoice):
    return signing.dumps(
        {"invoice_id": invoice.pk, "invoice_number": invoice.invoice_number},
        salt=INVOICE_LINK_SALT,
        compress=True,
    )


def invoice_pdf_token_data(token):
    max_age = getattr(settings, "INVOICE_LINK_MAX_AGE", 60 * 60 * 24 * 90)
    return signing.loads(token, salt=INVOICE_LINK_SALT, max_age=max_age)


def invoice_pdf_public_url(invoice):
    base_url = getattr(settings, "INVOICE_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        return ""
    path = reverse("electricity:public_invoice_pdf", kwargs={"token": invoice_pdf_token(invoice)})
    return f"{base_url}{path}"


def send_invoice_email(invoice):
    if not invoice.recipient_email:
        raise ValueError("The invoice does not have a recipient email address.")
    from_email = getattr(settings, "INVOICE_FROM_EMAIL", "Faktura@rwmel.se")
    customer_name = invoice.customer.full_name or "kund"
    currency = "kr" if invoice.currency.upper() == "SEK" else invoice.currency
    amount_due = f"{_sv_amount(invoice.amount_due)} {currency}"
    pdf_url = invoice_pdf_public_url(invoice)
    public_base_url = getattr(settings, "INVOICE_PUBLIC_BASE_URL", "https://www.rwmel.se").rstrip("/")
    context = {
        "invoice": invoice,
        "customer_name": customer_name,
        "amount_due": amount_due,
        "pdf_url": pdf_url,
        "logo_url": f"{public_base_url}/static/electricity/img/electricity_logo.jpg",
        "qr_url": f"{public_base_url}/static/electricity/img/invoice-payment-qr.jpg",
    }
    pdf_link_text = f"Öppna fakturan: {pdf_url}\n\n" if pdf_url else ""
    text_body = (
        f"Hej {customer_name},\n\n"
        "Tack för att du valde RWM EL – vi uppskattar verkligen ditt förtroende!\n\n"
        f"Fakturanummer: {invoice.invoice_number}\n"
        f"Att betala: {amount_due}\n"
        f"Förfallodatum: {invoice.due_date.isoformat()}\n"
        "Bankgiro: 5192-1302\n"
        f"Betalningsreferens: {invoice.invoice_number}\n\n"
        f"{pdf_link_text}"
        "Vänliga hälsningar,\nRWM EL\nRWM Helservice AB"
    )
    message = EmailMultiAlternatives(
        subject=f"Faktura {invoice.invoice_number} från RWM EL",
        body=text_body,
        from_email=from_email,
        to=[invoice.recipient_email],
        connection=invoice_email_connection(),
    )
    message.attach_alternative(
        render_to_string("electricity/email/invoice_email.html", context),
        "text/html",
    )
    message.attach(f"invoice-{invoice.invoice_number}.pdf", invoice_pdf_bytes(invoice), "application/pdf")
    sent_count = message.send(fail_silently=False)
    if sent_count != 1:
        raise RuntimeError("The email backend did not confirm that the invoice was sent.")
    invoice.status = Invoice.Status.SENT
    invoice.sent_at = timezone.now()
    invoice.save(update_fields=["status", "sent_at", "updated_at"])
    return True
