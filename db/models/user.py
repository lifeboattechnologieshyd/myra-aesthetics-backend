
import uuid

from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.db import models

from db.models import AuditModel


class CustomUserManager(BaseUserManager):
    def create_user(self, mobile, password=None, **extra_fields):
        if not mobile:
            raise ValueError("The Mobile Number must be set")
        user = self.model(mobile=mobile, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


class UserMaster(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=30)
    mobile = models.CharField(max_length=20, null=True, unique=True, blank=True)
    email = models.EmailField(max_length=100, unique=True, null=True)
    image = models.CharField(max_length=255, null=True)
    is_active = models.BooleanField(default=True)
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )
    points = models.IntegerField(default=0)
    updated_by = models.CharField(max_length=255,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bio = models.TextField(blank=True,null=True)
    objects = CustomUserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return str(self.email)

    class Meta:
        db_table = "user-master"