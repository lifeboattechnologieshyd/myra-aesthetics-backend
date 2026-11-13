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


]
