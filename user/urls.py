
from django.urls import path

from user.views.contact import ContactEnquiryAPIView, FileUploadView

urlpatterns = [
    path("contact/", ContactEnquiryAPIView.as_view()),
    path("file/upload", FileUploadView.as_view()),
]
