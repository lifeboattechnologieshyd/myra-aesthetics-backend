from django.contrib import admin
from django.urls import path, include
from backoffice.views.user import (
    LoginAPIView,
    CreateUserAPIView,
    ForgotPasswordAPIView,
    ResetUserPasswordAPIView
)
from backoffice.views.product import (
    ProductListCreateAPIView,
    ProductDetailAPIView,
)
from backoffice.views.patient import (
    PatientListCreateAPIView,
    PatientDetailAPIView,
)

from backoffice.views.appointment import (
    AppointmentListCreateAPIView,
    AppointmentDetailAPIView,
    PatientNextAppointmentAPIView
)

from backoffice.views.service import (
    ServiceListCreateAPIView,
    ServiceDetailAPIView
)

from backoffice.views.invoice import (
    InvoiceListCreateAPIView,
    InvoiceDetailAPIView
)

from backoffice.views.invoice_payment import (
    InvoicePaymentAPIView
)

from backoffice.views.reports import (
    DashboardReportAPIView,
    PatientRegistrationReportAPIView,
    PatientVisitReportAPIView,
    AppointmentSummaryReportAPIView,
    UpcomingAppointmentReportAPIView,
    PatientVisitHistoryAPIView,
    InvoiceReportAPIView,
    BillingSummaryReportAPIView
)

from backoffice.views.patient_visit import (
    PatientVisitListCreateAPIView,
    PatientVisitDetailAPIView,
)

from backoffice.views.patient_history import PatientHistoryAPIView

from backoffice.views.invoice_pdf import InvoicePDFAPIView
from backoffice.views.patient_visit import PatientVisitPhotoAPIView

urlpatterns = [
    #user urls
    path('login/', LoginAPIView.as_view()),
    path('create-user/', CreateUserAPIView.as_view()),
    path('forgot-password/', ForgotPasswordAPIView.as_view()),
    path('reset-user-password/',ResetUserPasswordAPIView.as_view()),

    #product urls
    path('products/', ProductListCreateAPIView.as_view()),
    path('products/<uuid:product_id>/', ProductDetailAPIView.as_view()),

    #patient profile urls
    path('patients/',PatientListCreateAPIView.as_view()),
    path('patients/<uuid:patient_id>/',PatientDetailAPIView.as_view()),

    #appointements urls
    path("appointments/",AppointmentListCreateAPIView.as_view()),
    path("appointments/<uuid:appointment_id>/",AppointmentDetailAPIView.as_view()),
    path('patients/<uuid:patient_id>/next-appointment/',PatientNextAppointmentAPIView.as_view()),

    path("services/",ServiceListCreateAPIView.as_view()),
    path("services/<uuid:service_id>/",ServiceDetailAPIView.as_view()),

    path("invoices/",InvoiceListCreateAPIView.as_view()),
    path("invoices/<uuid:invoice_id>/",InvoiceDetailAPIView.as_view()),
    path("invoices/<uuid:invoice_id>/payments/",InvoicePaymentAPIView.as_view()),

    #report_urls
    path("reports/dashboard/",DashboardReportAPIView.as_view()),
    path("reports/patients/",PatientRegistrationReportAPIView.as_view()),
    path("reports/visits/",PatientVisitReportAPIView.as_view()),
    path("reports/appointments/summary/",AppointmentSummaryReportAPIView.as_view()),
    path("reports/appointments/upcoming/",UpcomingAppointmentReportAPIView.as_view()),
    path("reports/patients/<uuid:patient_id>/visits/",PatientVisitHistoryAPIView.as_view()),
    path("reports/invoices/",InvoiceReportAPIView.as_view()),
    path("reports/billing/",BillingSummaryReportAPIView.as_view()),

    # Patient visit URLs
    path("patient-visits/", PatientVisitListCreateAPIView.as_view()),
    path("patient-visits/<uuid:visit_id>/",PatientVisitDetailAPIView.as_view()),

# Patient complete history
    path("patients/<uuid:patient_id>/history/",PatientHistoryAPIView.as_view()),

    path("invoices/<uuid:invoice_id>/pdf/",InvoicePDFAPIView.as_view()),

    path("patient-visits/<uuid:visit_id>/photos/",PatientVisitPhotoAPIView.as_view()),
]
