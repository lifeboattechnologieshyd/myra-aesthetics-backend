
from db.models.base import AuditModel
from django.db import models


class Product(AuditModel):

    product_name = models.CharField(max_length=255)

    description = models.TextField(
        blank=True,
        null=True
    )

    quantity = models.PositiveIntegerField()

    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product"

    def __str__(self):
        return self.product_name
