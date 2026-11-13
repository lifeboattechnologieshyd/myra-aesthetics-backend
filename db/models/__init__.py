from django.apps import AppConfig
from .user import UserMaster
from .patient import Patient
from .password_reset_request import PasswordResetRequest
from .product import Product
from .appointment import Appointment

class DbConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'db'