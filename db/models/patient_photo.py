
from django.db import models

from db.models.base import AuditModel
from db.models.patient import Patient
from db.models.patient_visit import PatientVisit


class PatientPhoto(AuditModel):

    class PhotoType(models.TextChoices):
        BEFORE = "BEFORE", "Before Treatment"
        AFTER = "AFTER", "After Treatment"
        OTHER = "OTHER", "Other"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="photos"
    )

    visit = models.ForeignKey(
        PatientVisit,
        on_delete=models.SET_NULL,
        related_name="photos",
        blank=True,
        null=True
    )

    #image = models.ImageField(
    #    upload_to="patient_photos/"
    #)

    photo_type = models.CharField(
        max_length=10,
        choices=PhotoType.choices,
        default=PhotoType.OTHER
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "patient_photo"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.patient.full_name} - {self.photo_type}"
