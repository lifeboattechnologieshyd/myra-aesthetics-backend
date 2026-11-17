
import re
from django.conf import settings

from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from db.models import ContactEnquiry
from shared.utils.custom_response import CustomResponse
from rest_framework.parsers import FormParser, MultiPartParser

from shared.utils.s3 import add_unique_suffix_to_filename, sanitize_filename


class ContactEnquiryAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request, format=None):

        # Read frontend fields
        full_name = request.data.get("fullName")
        phone = request.data.get("phone")
        email = request.data.get("email")
        treatment = request.data.get("treatment")
        doctor = request.data.get("doctor")
        preferred_date = request.data.get("preferredDate")
        preferred_time = request.data.get("preferredTime")
        message = request.data.get("message")
        permission = request.data.get("permission")
        source = request.data.get("source")

        # Validate required fields
        required_fields = {
            "fullName": full_name,
            "phone": phone,
            "treatment": treatment,
            "preferredDate": preferred_date,
            "preferredTime": preferred_time,
            "permission": permission,
            "source": source,
        }

        missing_fields = [
            field for field, value in required_fields.items()
            if value is None or (isinstance(value, str) and not value.strip())
        ]

        if missing_fields:
            return CustomResponse.error(
                message=f"Required fields are missing: {', '.join(missing_fields)}"
            )

        # Validate consent
        if permission is not True:
            return CustomResponse.error(
                message="Permission is required to submit the enquiry."
            )

        # Validate phone number
        phone = str(phone).strip()

        if not re.fullmatch(r"\+?[0-9]{7,15}", phone):
            return CustomResponse.error(
                message="Please provide a valid phone number."
            )

        # Validate email if provided
        if email:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError

            try:
                validate_email(email.strip())
            except ValidationError:
                return CustomResponse.error(
                    message="Please provide a valid email address."
                )

        # Validate preferred date
        preferred_date = parse_date(str(preferred_date))

        if not preferred_date:
            return CustomResponse.error(
                message="Invalid preferredDate. Use YYYY-MM-DD format."
            )

        if preferred_date < timezone.localdate():
            return CustomResponse.error(
                message="Preferred date cannot be in the past."
            )

        # Create contact enquiry
        enquiry = ContactEnquiry.objects.create(
            full_name=full_name.strip(),
            phone=phone,
            email=email.strip() if email else None,
            treatment=treatment.strip(),
            doctor=doctor.strip() if doctor else None,
            preferred_date=preferred_date,
            preferred_time=preferred_time.strip(),
            message=message.strip() if message else None,
            permission=True,
            source=source.strip()
        )

        return CustomResponse.success(
            message="Your enquiry has been submitted successfully.",
            data={
                "enquiry_id": str(enquiry.id),
                "fullName": enquiry.full_name,
                "phone": enquiry.phone,
                "email": enquiry.email,
                "treatment": enquiry.treatment,
                "doctor": enquiry.doctor,
                "preferredDate": enquiry.preferred_date,
                "preferredTime": enquiry.preferred_time,
                "message": enquiry.message,
                "permission": enquiry.permission,
                "source": enquiry.source,
                "created_at": enquiry.created_at
            }
        )


class FileUploadView(APIView):

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):

        files = request.FILES.getlist("files")
        path = request.data.get("path", "temp")



        if not files:
            return CustomResponse().success(
                {"error": "No file was provided."},
            )

        uploaded_files = []

        try:

            for file_obj in files:

                sanitized_filename = add_unique_suffix_to_filename(
                    sanitize_filename(file_obj.name)
                )

                file_path = default_storage.save(
                    f"{path}/{sanitized_filename}",
                    ContentFile(file_obj.read()),
                )

                file_url = settings.MEDIA_URL + file_path

                uploaded_files.append({
                    "original_filename": file_obj.name,
                    "file_url": file_url,
                    "file_path": file_path,
                })





            return CustomResponse().success(
                uploaded_files,
            )

        except Exception as e:



            return CustomResponse().error(
                {"error": str(e)},
            )
