from django.db import models
from db.models.base import AuditModel
from db.models.user import UserMaster


class PasswordResetRequest(AuditModel):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RESOLVED = "RESOLVED", "Resolved"

    user = models.ForeignKey(
        UserMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="password_reset_requests"
    )

    username = models.CharField(max_length=150)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    class Meta:
        db_table = "password_reset_request"

    def __str__(self):
        return self.username