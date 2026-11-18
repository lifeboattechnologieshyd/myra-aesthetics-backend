
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
import tempfile
import traceback

from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.files.base import ContentFile

from num2words import num2words
from playwright.sync_api import sync_playwright

from db.models import Invoice
from shared.utils.s3 import StoreS3Storage


# Import StoreS3Storage from your existing storage utility
# from your_project.storage import StoreS3Storage


def get_local_datetime(value):
    if not value:
        return None

    if timezone.is_naive(value):
        value = timezone.make_aware(
            value,
            timezone.get_current_timezone(),
        )

    return timezone.localtime(value)


def amount_in_words(amount):
    amount = Decimal(amount).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    words = num2words(
        rupees,
        lang="en_IN",
    ).title()

    if paise:
        paise_words = num2words(
            paise,
            lang="en_IN",
        ).title()

        return (
            f"Rupees {words} and "
            f"{paise_words} Paise Only"
        )

    return f"Rupees {words} Only"


def get_patient_name(patient):
    return (
        getattr(patient, "full_name", None)
        or getattr(patient, "name", None)
        or getattr(patient, "username", None)
        or "N/A"
    )


def generate_invoice_pdf(invoice_id):

    try:
        # --------------------------------------------------
        # Fetch invoice
        # --------------------------------------------------
        invoice = (
            Invoice.objects
            .select_related(
                "patient",
                "patient_visit",
            )
            .prefetch_related(
                "items",
                "payments",
            )
            .get(id=invoice_id)
        )

        invoice_items = list(invoice.items.all())
        invoice_payments = list(invoice.payments.all())

        # --------------------------------------------------
        # Calculate payment details
        # --------------------------------------------------
        amount_paid = sum(
            (
                payment.amount
                for payment in invoice_payments
            ),
            Decimal("0.00"),
        )

        balance_due = max(
            invoice.total_amount - amount_paid,
            Decimal("0.00"),
        )

        latest_payment = (
            invoice_payments[0]
            if invoice_payments
            else None
        )

        invoice_datetime = get_local_datetime(
            invoice.invoice_date
        )

        # --------------------------------------------------
        # Prepare template context
        # --------------------------------------------------
        context = {
            # Clinic details
            "clinic_name": getattr(
                settings,
                "CLINIC_NAME",
                "MYRAA AESTHETICS",
            ),
            "clinic_tagline": getattr(
                settings,
                "CLINIC_TAGLINE",
                "SKIN • HAIR • LASER",
            ),
            "clinic_address": getattr(
                settings,
                "CLINIC_ADDRESS",
                "Hanamkonda, Telangana",
            ),
            "clinic_contact": getattr(
                settings,
                "CLINIC_CONTACT",
                "00000 00000",
            ),
            "clinic_logo_url": getattr(
                settings,
                "CLINIC_LOGO_URL",
                "",
            ),

            # Invoice details
            "invoice_number": invoice.invoice_number,
            "invoice_date": (
                invoice_datetime.strftime("%d %b %Y")
                if invoice_datetime
                else "N/A"
            ),
            "invoice_time": (
                invoice_datetime.strftime("%I:%M %p")
                if invoice_datetime
                else "N/A"
            ),
            "billing_type": invoice.get_billing_type_display(),
            "payment_status": invoice.get_payment_status_display(),

            # Patient details
            "patient_name": get_patient_name(invoice.patient),
            "patient_mobile": (
                getattr(invoice.patient, "mobile", None)
                or "N/A"
            ),

            # Items
            "items": invoice_items,

            # Payment details
            "payment_mode": (
                latest_payment.get_payment_method_display()
                if latest_payment
                else "Pending"
            ),
            "receipt_number": (
                latest_payment.reference_number
                if latest_payment
                and latest_payment.reference_number
                else "N/A"
            ),
            "amount_received": amount_paid,
            "balance_due": balance_due,

            # Totals
            "subtotal": invoice.subtotal,
            "discount_amount": invoice.discount_amount,
            "taxable_amount": invoice.taxable_amount,
            "gst_rate": invoice.gst_rate,
            "gst_amount": invoice.gst_amount,
            "total_amount": invoice.total_amount,
            "amount_in_words": amount_in_words(
                invoice.total_amount
            ),
            "current_year": timezone.localdate().year,
        }

        # --------------------------------------------------
        # Render HTML
        # --------------------------------------------------
        html_content = render_to_string(
            "invoices/patient_invoice.html",
            context,
        )

        print("INVOICE HTML GENERATED")

        # --------------------------------------------------
        # Generate PDF
        # --------------------------------------------------
        with tempfile.TemporaryDirectory() as tmpdir:

            html_path = Path(tmpdir) / "invoice.html"
            pdf_path = (
                Path(tmpdir)
                / f"invoice_{invoice.invoice_number}.pdf"
            )

            html_path.write_text(
                html_content,
                encoding="utf-8",
            )

            with sync_playwright() as p:

                browser = p.chromium.launch(
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]
                )

                page = browser.new_page()

                page.goto(
                    html_path.as_uri(),
                    wait_until="networkidle",
                )

                page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={
                        "top": "5mm",
                        "bottom": "5mm",
                        "left": "5mm",
                        "right": "5mm",
                    },
                    scale=0.90,
                )

                browser.close()

            print("INVOICE PDF GENERATED:", pdf_path)

            # --------------------------------------------------
            # Upload PDF to S3
            # --------------------------------------------------


            storage = StoreS3Storage(
                bucket_name=settings.AWS_S3_BUCKET
            )

            file_key = (
                f"invoices/{invoice.invoice_number}.pdf"
            )

            with open(pdf_path, "rb") as pdf_file:

                file_path = storage.save(
                    file_key,
                    ContentFile(pdf_file.read()),
                )

            # Get S3 URL
            file_url = storage.url(file_path)

        # --------------------------------------------------
        # Save S3 URL in Invoice model
        # --------------------------------------------------
        invoice.invoice_pdf = file_url

        invoice.save(
            update_fields=["invoice_pdf"]
        )

        print("INVOICE UPLOADED:", file_url)

        return {
            "success": True,
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "invoice_pdf": file_url,
        }

    except Exception as error:

        print("INVOICE PDF GENERATION ERROR:", str(error))
        traceback.print_exc()

        return {
            "success": False,
            "message": "Unable to generate invoice PDF.",
        }
