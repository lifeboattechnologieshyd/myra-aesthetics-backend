
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator, EmptyPage
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from db.models import (
    Patient,
    Appointment,
    PatientVisit,
    PatientPhoto
)

from shared.utils.custom_response import CustomResponse


# =========================================================
# CONSTANTS
# =========================================================

CONSULTANT_NAME = "Dr. Mounika"

VISIT_FIELDS = {
    "appointment_id",
    "visit_date",
    "consultant_name",
    "notes",
}

REQUIRED_FIELDS = {
    "visit_date",
}


# =========================================================
# HELPER: FORMAT PATIENT VISIT RESPONSE
# =========================================================

def patient_visit_data(visit):

    appointment = visit.appointment

    photos = visit.photos.all()

    before_photos = []
    after_photos = []

    for photo in photos:

        photo_data = {
            "id": str(photo.id),
            "image_path": photo.image_path,
            "photo_type": photo.photo_type,
            "description": photo.description,
            "created_at": photo.created_at.isoformat(),
        }

        if photo.photo_type == PatientPhoto.PhotoType.BEFORE:
            before_photos.append(photo_data)

        elif photo.photo_type == PatientPhoto.PhotoType.AFTER:
            after_photos.append(photo_data)

    return {
        "id": str(visit.id),
        "patient_id": str(visit.patient_id),
        "patient_name": visit.patient.full_name,

        "appointment_id": (
            str(appointment.id) if appointment else None
        ),

        "appointment_datetime": (
            appointment.appointment_datetime.isoformat()
            if appointment else None
        ),

        "visit_date": visit.visit_date.isoformat(),
        "consultant_name": visit.consultant_name,
        "notes": visit.notes,

        "photos": {
            "before": before_photos,
            "after": after_photos,
        },

        "created_at": visit.created_at.isoformat(),
        "updated_at": visit.updated_at.isoformat(),
        "created_by": visit.created_by,
        "updated_by": visit.updated_by,
    }


# =========================================================
# HELPER: VALIDATE PATIENT VISIT DATA
# =========================================================

def validate_visit_data(data, partial=False):

    unknown_fields = set(data.keys()) - VISIT_FIELDS

    if unknown_fields:
        raise ValueError(
            f"Unknown fields: {', '.join(unknown_fields)}"
        )

    if not partial:

        missing_fields = REQUIRED_FIELDS - set(data.keys())

        if missing_fields:
            raise ValueError(
                f"Required fields missing: {', '.join(missing_fields)}"
            )

    values = {}

    for field in VISIT_FIELDS:

        if field not in data:
            continue

        value = data[field]

        # -------------------------------------------------
        # VALIDATE APPOINTMENT
        # -------------------------------------------------

        if field == "appointment_id":

            if value in ("", None):
                values["appointment"] = None
                continue

            try:
                appointment = Appointment.objects.filter(
                    id=value
                ).select_related("patient").first()

            except (ValueError, DjangoValidationError):
                raise ValueError("Invalid appointment_id.")

            if appointment is None:
                raise ValueError("Appointment not found.")

            values["appointment"] = appointment

        # -------------------------------------------------
        # VALIDATE VISIT DATE
        # -------------------------------------------------

        elif field == "visit_date":

            if not isinstance(value, str):
                raise ValueError(
                    "visit_date must be a valid ISO datetime."
                )

            visit_date = parse_datetime(value.strip())

            if visit_date is None:
                raise ValueError(
                    "Invalid visit_date. Use ISO format, "
                    "for example 2026-11-17T10:30:00+05:30."
                )

            if timezone.is_naive(visit_date):
                visit_date = timezone.make_aware(
                    visit_date,
                    timezone.get_current_timezone()
                )

            values["visit_date"] = visit_date

        # -------------------------------------------------
        # CONSULTANT NAME IS STATIC
        # -------------------------------------------------

        elif field == "consultant_name":

            values["consultant_name"] = CONSULTANT_NAME

        # -------------------------------------------------
        # VALIDATE NOTES
        # -------------------------------------------------

        elif field == "notes":

            if value is not None and not isinstance(value, str):
                raise ValueError(
                    "notes must be a string."
                )

            values["notes"] = value.strip() if value else None

    # Always use the static consultant name.
    values["consultant_name"] = CONSULTANT_NAME

    return values


# =========================================================
# HELPER: VALIDATE MODEL
# =========================================================

def get_visit_model_errors(visit):

    try:
        visit.full_clean()
        return None

    except DjangoValidationError as error:
        return error.message_dict


# =========================================================
# API 1: PATIENT VISIT LIST AND CREATION
# =========================================================

class PatientVisitListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # POST: CREATE PATIENT VISIT
    # -----------------------------------------------------

    def post(self, request, format=None):

        try:

            patient_id = request.data.get("patient_id")

            if not patient_id:
                return CustomResponse.error(
                    message="patient_id is required."
                )

            try:
                patient = Patient.objects.filter(
                    id=patient_id,
                    is_active=True
                ).first()

            except (ValueError, DjangoValidationError):
                return CustomResponse.error(
                    message="Invalid patient_id."
                )

            if patient is None:
                return CustomResponse.error(
                    message="Active patient not found."
                )

            # Remove patient_id because it is handled separately.
            visit_input = request.data.copy()
            visit_input.pop("patient_id", None)

            values = validate_visit_data(visit_input)

            # -------------------------------------------------
            # VALIDATE APPOINTMENT AND PREVENT DUPLICATE VISITS
            # -------------------------------------------------

            appointment = values.get("appointment")

            if appointment:

                if appointment.patient_id != patient.id:
                    return CustomResponse.error(
                        message=(
                            "The selected appointment does not belong "
                            "to this patient."
                        )
                    )

                if PatientVisit.objects.filter(
                    appointment=appointment
                ).exists():
                    return CustomResponse.error(
                        message=(
                            "A patient visit already exists for this "
                            "appointment. Please update the existing visit."
                        )
                    )

            # Create visit.
            visit = PatientVisit(
                patient=patient,
                **values,
                created_by=request.user.username,
                updated_by=request.user.username
            )

            errors = get_visit_model_errors(visit)

            if errors:
                return CustomResponse.error(
                    message="Patient visit validation failed.",
                    errors=errors
                )

            visit.save()

            return CustomResponse.success(
                message="Patient visit created successfully.",
                data=patient_visit_data(visit)
            )

        except ValueError as error:

            return CustomResponse.error(
                message=str(error)
            )

    # -----------------------------------------------------
    # GET: RETRIEVE PATIENT VISITS
    # -----------------------------------------------------

    def get(self, request, format=None):

        queryset = PatientVisit.objects.select_related(
            "patient",
            "appointment"
        ).prefetch_related(
            "photos"
        ).all()

        # FILTER BY PATIENT
        patient_id = request.query_params.get("patient_id")

        if patient_id:

            try:
                queryset = queryset.filter(
                    patient_id=patient_id
                )

            except (ValueError, DjangoValidationError):
                return CustomResponse.error(
                    message="Invalid patient_id."
                )

        # FILTER BY VISIT DATE RANGE
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if start_date or end_date:

            if not start_date or not end_date:
                return CustomResponse.error(
                    message=(
                        "Both start_date and end_date are required."
                    )
                )

            start = parse_date(start_date)
            end = parse_date(end_date)

            if not start or not end:
                return CustomResponse.error(
                    message="Dates must use YYYY-MM-DD format."
                )

            if start > end:
                return CustomResponse.error(
                    message="start_date cannot be after end_date."
                )

            queryset = queryset.filter(
                visit_date__date__range=(start, end)
            )

        # PAGINATION
        try:

            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("size", 20))

            if page < 1:
                raise ValueError

            if size < 1 or size > 100:
                raise ValueError

        except (ValueError, TypeError):

            return CustomResponse.error(
                message=(
                    "Invalid pagination values. Page must be positive "
                    "and size must be between 1 and 100."
                )
            )

        paginator = Paginator(queryset, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:
            return CustomResponse.error(
                message="Requested page does not exist."
            )

        results = [
            patient_visit_data(visit)
            for visit in page_obj
        ]

        return CustomResponse.success(
            message="Patient visits retrieved successfully.",
            data={
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page,
                "page_size": size,
                "results": results
            }
        )


# =========================================================
# API 2: PATIENT VISIT RETRIEVAL AND UPDATION
# =========================================================

class PatientVisitDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get_visit(self, visit_id):

        try:
            return PatientVisit.objects.select_related(
                "patient",
                "appointment"
            ).prefetch_related(
                "photos"
            ).filter(id=visit_id).first()

        except (ValueError, DjangoValidationError):
            return None

    # -----------------------------------------------------
    # GET: RETRIEVE ONE PATIENT VISIT
    # -----------------------------------------------------

    def get(self, request, visit_id, format=None):

        visit = self.get_visit(visit_id)

        if visit is None:
            return CustomResponse.error(
                message="Patient visit not found."
            )

        return CustomResponse.success(
            message="Patient visit retrieved successfully.",
            data=patient_visit_data(visit)
        )

    # -----------------------------------------------------
    # PATCH: UPDATE PATIENT VISIT
    # -----------------------------------------------------

    def patch(self, request, visit_id, format=None):

        visit = self.get_visit(visit_id)

        if visit is None:
            return CustomResponse.error(
                message="Patient visit not found."
            )

        if not request.data:
            return CustomResponse.error(
                message="At least one field is required."
            )

        try:

            values = validate_visit_data(
                request.data,
                partial=True
            )

            appointment = values.get(
                "appointment",
                visit.appointment
            )

            # Ensure appointment belongs to the same patient.
            if appointment and appointment.patient_id != visit.patient_id:
                return CustomResponse.error(
                    message=(
                        "The selected appointment does not belong "
                        "to this patient."
                    )
                )

            # Prevent linking another visit to an appointment
            # that already has a different visit.
            if appointment and PatientVisit.objects.filter(
                appointment=appointment
            ).exclude(
                id=visit.id
            ).exists():
                return CustomResponse.error(
                    message=(
                        "A patient visit already exists for this "
                        "appointment."
                    )
                )

            for field, value in values.items():
                setattr(visit, field, value)

            visit.updated_by = request.user.username

            errors = get_visit_model_errors(visit)

            if errors:
                return CustomResponse.error(
                    message="Patient visit validation failed.",
                    errors=errors
                )

            visit.save()

            return CustomResponse.success(
                message="Patient visit updated successfully.",
                data=patient_visit_data(visit)
            )

        except ValueError as error:

            return CustomResponse.error(
                message=str(error)
            )


# =========================================================
# API 3: ADD PHOTOS TO PATIENT VISIT
# =========================================================

class PatientVisitPhotoAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # POST: ADD PHOTO TO PATIENT VISIT
    # -----------------------------------------------------

    def post(self, request, visit_id, format=None):

        # FIND PATIENT VISIT
        try:
            visit = PatientVisit.objects.select_related(
                "patient"
            ).filter(id=visit_id).first()

        except (ValueError, DjangoValidationError):
            return CustomResponse.error(
                message="Invalid visit_id."
            )

        if visit is None:
            return CustomResponse.error(
                message="Patient visit not found."
            )

        # GET INPUT DATA
        image_path = request.data.get("image_path")
        photo_type = request.data.get("photo_type")
        description = request.data.get("description")

        # VALIDATE IMAGE PATH
        if not isinstance(image_path, str) or not image_path.strip():
            return CustomResponse.error(
                message="image_path is required."
            )

        image_path = image_path.strip()

        if len(image_path) > 500:
            return CustomResponse.error(
                message="image_path cannot exceed 500 characters."
            )

        # VALIDATE PHOTO TYPE
        if not isinstance(photo_type, str):
            return CustomResponse.error(
                message="photo_type is required. Use BEFORE or AFTER."
            )

        photo_type = photo_type.strip().upper()

        if photo_type not in PatientPhoto.PhotoType.values:
            return CustomResponse.error(
                message="Invalid photo_type. Use BEFORE or AFTER."
            )

        # VALIDATE DESCRIPTION
        if description is not None and not isinstance(description, str):
            return CustomResponse.error(
                message="description must be a string."
            )

        if description is not None:
            description = description.strip() or None

        existing_photo = PatientPhoto.objects.filter(
            patient=visit.patient,
            visit=visit,
            image_path=image_path,
            photo_type=photo_type
        ).first()

        if existing_photo:
            return CustomResponse.success(
                message="This photo is already added to the patient visit.",
                data={
                    "photo_id": str(existing_photo.id),
                    "patient_id": str(existing_photo.patient_id),
                    "visit_id": str(existing_photo.visit_id),
                    "photo_type": existing_photo.photo_type,
                    "image_path": existing_photo.image_path,
                    "description": existing_photo.description,
                    "created_at": existing_photo.created_at.isoformat()
                }
            )

        # CREATE PATIENT PHOTO
        photo = PatientPhoto(
            patient=visit.patient,
            visit=visit,
            image_path=image_path,
            photo_type=photo_type,
            description=description,
            created_by=request.user.username,
            updated_by=request.user.username
        )

        try:

            photo.full_clean()
            photo.save()

        except DjangoValidationError as error:

            return CustomResponse.error(
                message="Patient photo validation failed.",
                errors=error.message_dict
            )

        return CustomResponse.success(
            message="Patient photo added successfully.",
            data={
                "photo_id": str(photo.id),
                "patient_id": str(photo.patient_id),
                "visit_id": str(photo.visit_id),
                "photo_type": photo.photo_type,
                "image_path": photo.image_path,
                "description": photo.description,
                "created_at": photo.created_at.isoformat()
            }
        )
