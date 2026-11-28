
from django.db import models
from db.models.base import AuditModel
from db.models.patient import Patient


class Appointment(AuditModel):

    # Available appointment statuses.
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NOT_ATTENDED = "NOT_ATTENDED", "Not Attended"

    # Connect each appointment to its registered patient.
    # PROTECT prevents deletion of a patient who has appointments.
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="appointments"
    )

    # Stores the appointment date and time together.
    appointment_datetime = models.DateTimeField()

    # Consultation or treatment notes can be added after completion.
    # This field is optional because notes may not be available yet.
    notes = models.TextField(
        blank=True,
        null=True
    )

    # Every new appointment starts with SCHEDULED status.
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED
    )

    class Meta:
        db_table = "appointment"
        ordering = ["appointment_datetime"]

    def __str__(self):
        return f"{self.patient.full_name} - {self.appointment_datetime}"
