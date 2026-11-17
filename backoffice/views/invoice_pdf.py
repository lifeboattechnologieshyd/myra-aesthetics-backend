
from io import BytesIO
from decimal import Decimal
import logging

from urllib.request import Request, urlopen

from django.http import HttpResponse
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Image
)

from db.models import Invoice


import ssl
import certifi
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


# =========================================================
# CLINIC DETAILS
# =========================================================

CLINIC_NAME = "MYRAA Aesthetics"

CLINIC_ADDRESS = (
    "1st Floor, Kapil Kakatiya Towers, "
    "Beside Barbeque Nation, Nakkalagutta, "
    "Hanamkonda, Warangal - 506001"
)

CLINIC_PHONE = "91 81919 66999"

CLINIC_EMAIL = "myraaaesthetics@gmail.com"

CLINIC_LOGO_URL = "https://myra-development.s3.ap-south-1.amazonaws.com/temp/WhatsApp_Image_2026-11-17_at_10.43.59_AM_0bbc7fa4.jpeg"


# =========================================================
# FETCH CLINIC LOGO FROM S3
# =========================================================

def get_clinic_logo():

    try:

        request = Request(
            CLINIC_LOGO_URL,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urlopen(request, timeout=20) as response:

            if response.status != 200:
                raise ValueError(
                    f"S3 returned status: {response.status}"
                )

            image_data = response.read(5 * 1024 * 1024 + 1)

        # Maximum image size: 5 MB
        if len(image_data) > 5 * 1024 * 1024:
            raise ValueError("Clinic logo exceeds 5 MB.")

        if not image_data:
            raise ValueError("Downloaded clinic logo is empty.")

        # Create image buffer
        image_buffer = BytesIO(image_data)

        # Read actual image dimensions
        image_reader = ImageReader(image_buffer)

        image_width, image_height = image_reader.getSize()

        if not image_width or not image_height:
            raise ValueError("Invalid clinic logo dimensions.")

        # Desired logo dimensions in PDF
        max_width = 35 * mm
        max_height = 35 * mm

        # Maintain original aspect ratio
        scale = min(
            max_width / image_width,
            max_height / image_height
        )

        logo_width = image_width * scale
        logo_height = image_height * scale

        # Use a fresh buffer for ReportLab Image
        logo_buffer = BytesIO(image_data)

        logo = Image(
            logo_buffer,
            width=logo_width,
            height=logo_height
        )

        logo.hAlign = "CENTER"

        return logo

    except Exception:

        logger.exception(
            "Failed to load MYRAA clinic logo from S3."
        )

        return None


# =========================================================
# FORMAT MONEY
# =========================================================

def format_money(value):

    return f"Rs. {Decimal(str(value)):,.2f}"


# =========================================================
# NUMBER TO WORDS
# INDIAN NUMBERING SYSTEM
# =========================================================

def number_to_words(number):

    ones = [
        "", "One", "Two", "Three", "Four",
        "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen",
        "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]

    tens = [
        "", "", "Twenty", "Thirty", "Forty",
        "Fifty", "Sixty", "Seventy", "Eighty",
        "Ninety"
    ]

    def under_thousand(n):

        words = []

        if n >= 100:
            words.append(ones[n // 100] + " Hundred")
            n %= 100

        if n >= 20:
            words.append(tens[n // 10])
            n %= 10

        if n > 0:
            words.append(ones[n])

        return " ".join(words)

    if number == 0:
        return "Zero"

    parts = []

    crore = number // 10000000
    number %= 10000000

    lakh = number // 100000
    number %= 100000

    thousand = number // 1000
    number %= 1000

    if crore:
        parts.append(under_thousand(crore) + " Crore")

    if lakh:
        parts.append(under_thousand(lakh) + " Lakh")

    if thousand:
        parts.append(under_thousand(thousand) + " Thousand")

    if number:
        parts.append(under_thousand(number))

    return " ".join(parts)


def amount_in_words(amount):

    amount = Decimal(str(amount)).quantize(
        Decimal("0.01")
    )

    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    result = number_to_words(rupees) + " Rupees"

    if paise:
        result += " and " + number_to_words(paise) + " Paise"

    return result + " Only"


# =========================================================
# CALCULATE PATIENT AGE
# =========================================================

def calculate_age(date_of_birth, reference_date):

    if not date_of_birth:
        return "N/A"

    age = reference_date.year - date_of_birth.year

    if (
        (reference_date.month, reference_date.day)
        < (date_of_birth.month, date_of_birth.day)
    ):
        age -= 1

    return str(age)


# =========================================================
# PDF GENERATION API
# =========================================================

class InvoicePDFAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id, format=None):

        invoice = Invoice.objects.select_related(
            "patient",
            "patient_visit"
        ).prefetch_related(
            "items",
            "payments"
        ).filter(
            id=invoice_id
        ).first()

        if not invoice:
            return HttpResponse(
                "Invoice not found",
                status=404
            )

        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=12 * mm,
            bottomMargin=15 * mm
        )

        styles = getSampleStyleSheet()

        clinic_style = ParagraphStyle(
            "Clinic",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=19,
            leading=23,
            textColor=colors.HexColor("#263746")
        )

        normal_style = ParagraphStyle(
            "NormalCustom",
            parent=styles["Normal"],
            fontSize=10,
            leading=11
        )

        heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=12,
            leading=13,
            textColor=colors.HexColor("#263746")
        )

        right_style = ParagraphStyle(
            "Right",
            parent=normal_style,
            alignment=TA_RIGHT
        )

        center_style = ParagraphStyle(
            "Center",
            parent=normal_style,
            alignment=TA_CENTER
        )

        elements = []

        # -------------------------------------------------
        # CLINIC HEADER WITH LOGO
        # -------------------------------------------------

        logo = get_clinic_logo()

        if logo:

            elements.append(logo)

            elements.append(
                Spacer(1, 5)
            )

        elements.append(
            Paragraph(
                CLINIC_NAME,
                clinic_style
            )
        )

        elements.append(
            Spacer(1, 3)
        )

        elements.append(
            Paragraph(
                CLINIC_ADDRESS,
                center_style
            )
        )

        elements.append(
            Paragraph(
                f"Phone: {CLINIC_PHONE} | Email: {CLINIC_EMAIL}",
                center_style
            )
        )

        elements.append(
            Spacer(1, 8)
        )

        elements.append(
            HRFlowable(
                width="100%",
                thickness=1,
                color=colors.HexColor("#263746")
            )
        )

        elements.append(
            Spacer(1, 8)
        )

        # -------------------------------------------------
        # INVOICE DETAILS
        # -------------------------------------------------

        local_invoice_date = timezone.localtime(
            invoice.invoice_date
        )

        invoice_details = [
            [
                Paragraph(
                    "<b>INVOICE</b>",
                    heading_style
                ),
                Paragraph(
                    f"<b>Invoice No:</b> {invoice.invoice_number}",
                    right_style
                )
            ],
            [
                Paragraph(
                    f"<b>Date:</b> {local_invoice_date.strftime('%d-%m-%Y')}",
                    normal_style
                ),
                Paragraph(
                    f"<b>Time:</b> {local_invoice_date.strftime('%I:%M %p')}",
                    right_style
                )
            ]
        ]

        invoice_table = Table(
            invoice_details,
            colWidths=[90 * mm, 90 * mm]
        )

        invoice_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
            ])
        )

        elements.append(invoice_table)

        elements.append(
            Spacer(1, 8)
        )

        # -------------------------------------------------
        # PATIENT DETAILS
        # -------------------------------------------------

        patient = invoice.patient

        age = calculate_age(
            patient.date_of_birth,
            local_invoice_date.date()
        )

        consultant_name = (
            invoice.patient_visit.consultant_name
            if invoice.patient_visit_id
            else "-"
        )

        patient_data = [
            [
                Paragraph(
                    "<b>Patient Details</b>",
                    heading_style
                ),
                ""
            ],
            [
                Paragraph(
                    f"<b>Patient Name:</b> {patient.full_name}",
                    normal_style
                ),
                Paragraph(
                    f"<b>Mobile:</b> {patient.mobile}",
                    normal_style
                )
            ],
            [
                Paragraph(
                    f"<b>Age:</b> {age} years",
                    normal_style
                ),
                Paragraph(
                    f"<b>Gender:</b> {patient.gender}",
                    normal_style
                )
            ],
            [
                Paragraph(
                    f"<b>Consultant:</b> {consultant_name}",
                    normal_style
                ),
                ""
            ]
        ]

        patient_table = Table(
            patient_data,
            colWidths=[90 * mm, 90 * mm]
        )

        patient_table.setStyle(
            TableStyle([
                ("SPAN", (0, 0), (1, 0)),
                ("SPAN", (0, 3), (1, 3)),
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#EAF0F4")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 1), (-1, -1), 0.3, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
            ])
        )

        elements.append(patient_table)

        # -------------------------------------------------
        # INVOICE ITEMS
        # -------------------------------------------------

        elements.append(
            Spacer(1, 12)
        )

        elements.append(
            Paragraph(
                "Billing Details",
                heading_style
            )
        )

        item_rows = [[
            "Description",
            "Qty",
            "Rate",
            "GST %",
            "GST Amount",
            "Amount"
        ]]

        for item in invoice.items.all():

            item_rows.append([
                Paragraph(item.item_name, normal_style),
                str(item.quantity),
                format_money(item.unit_price),
                f"{item.gst_rate}%",
                format_money(item.gst_amount),
                format_money(item.total_price)
            ])

        item_table = Table(
            item_rows,
            colWidths=[
                49 * mm,
                12 * mm,
                27 * mm,
                19 * mm,
                30 * mm,
                35 * mm
            ],
            repeatRows=1
        )

        item_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#263746")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
            ])
        )

        elements.append(item_table)

        # -------------------------------------------------
        # BILL SUMMARY
        # -------------------------------------------------

        elements.append(
            Spacer(1, 10)
        )

        summary_rows = [
            ["Subtotal", format_money(invoice.subtotal)],
            ["Discount", format_money(invoice.discount_amount)],
            ["Taxable Amount", format_money(invoice.taxable_amount)],
            ["Total GST", format_money(invoice.gst_amount)],
            ["Grand Total", format_money(invoice.total_amount)]
        ]

        summary_table = Table(
            summary_rows,
            colWidths=[130 * mm, 42 * mm]
        )

        summary_table.setStyle(
            TableStyle([
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
            ])
        )

        elements.append(summary_table)

        # -------------------------------------------------
        # PAYMENT DETAILS
        # -------------------------------------------------

        elements.append(
            Spacer(1, 12)
        )

        elements.append(
            Paragraph(
                "Payment Details",
                heading_style
            )
        )

        payment_rows = [[
            "Date",
            "Payment Mode",
            "Reference Number",
            "Amount"
        ]]

        payments = list(invoice.payments.all())

        for payment in payments:

            payment_date = timezone.localtime(
                payment.payment_date
            )

            payment_rows.append([
                payment_date.strftime("%d-%m-%Y"),
                payment.payment_method,
                payment.reference_number or "N/A",
                format_money(payment.amount)
            ])

        if not payments:

            payment_rows.append([
                "N/A",
                "Not Paid",
                "N/A",
                format_money(0)
            ])

        payment_table = Table(
            payment_rows,
            colWidths=[
                32 * mm,
                40 * mm,
                65 * mm,
                35 * mm
            ],
            repeatRows=1
        )

        payment_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#263746")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
            ])
        )

        elements.append(payment_table)

        paid_amount = sum(
            (payment.amount for payment in payments),
            Decimal("0.00")
        )

        balance_amount = (
            invoice.total_amount - paid_amount
        )

        elements.append(
            Spacer(1, 8)
        )

        payment_summary = [
            [
                "Amount Paid",
                format_money(paid_amount)
            ],
            [
                "Balance Due",
                format_money(balance_amount)
            ]
        ]

        payment_summary_table = Table(
            payment_summary,
            colWidths=[130 * mm, 42 * mm]
        )

        payment_summary_table.setStyle(
            TableStyle([
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
            ])
        )

        elements.append(payment_summary_table)

        # -------------------------------------------------
        # AMOUNT IN WORDS
        # -------------------------------------------------

        elements.append(
            Spacer(1, 10)
        )

        elements.append(
            Paragraph(
                f"<b>Amount in Words:</b> "
                f"{amount_in_words(invoice.total_amount)}",
                normal_style
            )
        )

        # -------------------------------------------------
        # SIGNATURE SECTION
        # -------------------------------------------------

        elements.append(
            Spacer(1, 35)
        )

        signature_data = [[
            Paragraph(
                "________________________<br/>"
                "Patient Signature",
                center_style
            ),
            Paragraph(
                "________________________<br/>"
                "Authorized Signature",
                center_style
            )
        ]]

        signature_table = Table(
            signature_data,
            colWidths=[85 * mm, 85 * mm]
        )

        signature_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM")
            ])
        )

        elements.append(signature_table)

        # -------------------------------------------------
        # BUILD PDF
        # -------------------------------------------------

        document.build(elements)

        pdf = buffer.getvalue()

        buffer.close()

        response = HttpResponse(
            pdf,
            content_type="application/pdf"
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.invoice_number}.pdf"'
        )

        return response
