
from django.db import models

from db.models import PatientVisit
from db.models.base import AuditModel
from db.models.patient import Patient


class Invoice(AuditModel):

    class BillingType(models.TextChoices):
        GST = "GST", "GST"
        NON_GST = "NON_GST", "Non-GST"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
        PAID = "PAID", "Paid"

    patient_visit = models.ForeignKey(
        PatientVisit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices"
    )

    invoice_number = models.CharField(
        max_length=30,
        unique=True
    )

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="invoices"
    )

    invoice_date = models.DateTimeField()

    billing_type = models.CharField(
        max_length=10,
        choices=BillingType.choices
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    taxable_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    gst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    invoice_pdf = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "invoice"
        ordering = ["-invoice_date"]

    def __str__(self):
        return self.invoice_number
