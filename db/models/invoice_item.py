
from django.db import models

from db.models.base import AuditModel
from db.models.invoice import Invoice
from db.models.service import Service
from db.models.product import Product


class InvoiceItem(AuditModel):

    class ItemType(models.TextChoices):
        CONSULTATION = "CONSULTATION", "Consultation"
        TREATMENT = "TREATMENT", "Treatment"
        PRODUCT = "PRODUCT", "Product"
        CUSTOM = "CUSTOM", "Custom"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items"
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        related_name="invoice_items",
        blank=True,
        null=True
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name="invoice_items",
        blank=True,
        null=True
    )

    item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices
    )

    item_name = models.CharField(max_length=200)

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
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

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    class Meta:
        db_table = "invoice_item"

    def __str__(self):
        return self.item_name
