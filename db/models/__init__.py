from django.apps import AppConfig
from .user import UserMaster
from .patient import Patient
from .password_reset_request import PasswordResetRequest
from .product import Product
from .appointment import Appointment
from .patient_visit import PatientVisit
from .patient_photo import PatientPhoto
from .service import Service
from .invoice import Invoice
from .invoice_item import InvoiceItem
from .invoice_payment import InvoicePayment
from .contact_enquiry import ContactEnquiry

class DbConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'db'