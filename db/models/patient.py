
from django.db import models
from db.models.base import AuditModel


class Patient(AuditModel):

    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        OTHER = "OTHER", "Other"

    full_name = models.CharField(max_length=255)

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank = True,
        null = True
    )

    mobile = models.CharField(max_length=20)

    alternate_mobile = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    email = models.EmailField(
        max_length=255,
        blank=True,
        null=True
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "patient"

    def __str__(self):
        return self.full_name
