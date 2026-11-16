
from django.urls import path

from user.views.contact import ContactEnquiryAPIView


urlpatterns = [
    path("contact/", ContactEnquiryAPIView.as_view()),
]
