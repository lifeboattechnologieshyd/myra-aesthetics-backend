
from django.db import models

from db.models.base import AuditModel
from db.models.patient import Patient
from db.models.appointment import Appointment


class PatientVisit(AuditModel):

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="visits"
    )

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        related_name="visits",
        blank=True,
        null=True
    )

    visit_date = models.DateTimeField()

    consultant_name = models.CharField(
        max_length=150
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "patient_visit"
        ordering = ["-visit_date"]

    def __str__(self):
        return f"{self.patient.full_name} - {self.visit_date}"
