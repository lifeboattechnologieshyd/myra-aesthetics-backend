
from django.db import models

from db.models.base import AuditModel


class Service(AuditModel):

    class ServiceType(models.TextChoices):
        CONSULTATION = "CONSULTATION", "Consultation"
        TREATMENT = "TREATMENT", "Treatment"

    service_name = models.CharField(max_length=150)

    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "service"
        ordering = ["service_name"]

    def __str__(self):
        return self.service_name
