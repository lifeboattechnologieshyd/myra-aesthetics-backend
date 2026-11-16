
from django.db import models

from .base import AuditModel


class ContactEnquiry(AuditModel):

    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=254, blank=True, null=True)

    treatment = models.CharField(max_length=150)
    doctor = models.CharField(max_length=150, blank=True, null=True)

    preferred_date = models.DateField()
    preferred_time = models.CharField(max_length=30)

    message = models.TextField(blank=True, null=True)

    permission = models.BooleanField(default=False)
    source = models.CharField(max_length=150)

    class Meta:
        db_table = "contact_enquiry"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} - {self.treatment}"
