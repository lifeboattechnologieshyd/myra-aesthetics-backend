
from django.db import models

from db.models.base import AuditModel
from db.models.invoice import Invoice


class InvoicePayment(AuditModel):

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        CARD = "CARD", "Card"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices
    )

    payment_date = models.DateTimeField()

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    class Meta:
        db_table = "invoice_payment"
        ordering = ["-payment_date"]

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount}"
