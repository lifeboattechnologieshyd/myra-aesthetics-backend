
# =========================================================
# IMPORTS
# =========================================================

from django.core.paginator import Paginator, EmptyPage
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from db.models.appointment import Appointment
from db.models.patient import Patient
from db.models.patient_visit import PatientVisit
from db.models.patient_photo import PatientPhoto

from shared.utils.custom_response import CustomResponse


# =========================================================
# CONSTANTS
# =========================================================

CONSULTANT_NAME = "Dr. Mounika"

# =========================================================
# CUSTOM EXCEPTION FOR TRANSACTION VALIDATION
# =========================================================

class TransactionValidationError(Exception):

    def __init__(self, message, errors=None):
        self.message = message
        self.errors = errors
        super().__init__(message)


# =========================================================
# HELPER 1: SHORT DISPLAY ID
# =========================================================

def short_id(value):
    return str(value)[:8].upper()


# =========================================================
# HELPER 2: FORMAT APPOINTMENT RESPONSE
# =========================================================

def appointment_data(appointment):

    visit = appointment.visits.all().first()

    visit_data = None

    if visit:

        before_photos = []
        after_photos = []

        for photo in visit.photos.all():

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

        visit_data = {
            "id": str(visit.id),
            "visit_date": visit.visit_date.isoformat(),
            "consultant_name": visit.consultant_name,
            "notes": visit.notes,
            "photos": {
                "before": before_photos,
                "after": after_photos,
            }
        }

    return {
        "id": str(appointment.id),
        "display_id": short_id(appointment.id),
        "patient_id": str(appointment.patient.id),
        "patient_name": appointment.patient.full_name,
        "appointment_datetime": appointment.appointment_datetime.isoformat(),
        "notes": appointment.notes,
        "status": appointment.status,
        "visit": visit_data,
        "created_at": appointment.created_at.isoformat(),
        "updated_at": appointment.updated_at.isoformat(),
        "created_by": appointment.created_by,
        "updated_by": appointment.updated_by
    }


# =========================================================
# HELPER 3: VALIDATE APPOINTMENT DATA
# =========================================================

def validate_appointment_data(data, operation="create", partial=False):

    create_fields = {
        "patient_id",
        "appointment_datetime"
    }

    update_fields = {
        "appointment_datetime",
        "status",
        "notes",
        "photos"
    }

    allowed_fields = (
        create_fields if operation == "create"
        else update_fields
    )

    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        return None, {
            "error": f"Unknown field(s): {', '.join(unknown_fields)}"
        }

    if operation == "create":

        missing_fields = create_fields - set(data.keys())

        if missing_fields:
            return None, {
                "error": f"Missing field(s): {', '.join(missing_fields)}"
            }

    elif not partial:

        required_fields = {
            "appointment_datetime",
            "status"
        }

        missing_fields = required_fields - set(data.keys())

        if missing_fields:
            return None, {
                "error": f"Missing field(s): {', '.join(missing_fields)}"
            }

    elif not data:

        return None, {
            "error": "At least one field is required."
        }

    validated_data = {}

    # -----------------------------------------------------
    # VALIDATE APPOINTMENT DATE AND TIME
    # -----------------------------------------------------

    if "appointment_datetime" in data:

        date_time_value = data.get("appointment_datetime")

        if not isinstance(date_time_value, str) or not date_time_value.strip():
            return None, {
                "appointment_datetime": "Appointment date and time are required."
            }

        appointment_datetime = parse_datetime(date_time_value.strip())

        if appointment_datetime is None:
            return None, {
                "appointment_datetime": (
                    "Enter a valid ISO 8601 date-time. "
                    "Example: 2026-11-20T10:30:00+05:30"
                )
            }

        if timezone.is_naive(appointment_datetime):
            appointment_datetime = timezone.make_aware(
                appointment_datetime,
                timezone.get_current_timezone()
            )

        validated_data["appointment_datetime"] = appointment_datetime

    # -----------------------------------------------------
    # VALIDATE APPOINTMENT STATUS
    # -----------------------------------------------------

    if "status" in data:

        appointment_status = data.get("status")

        allowed_statuses = Appointment.Status.values

        if appointment_status not in allowed_statuses:
            return None, {
                "status": (
                    f"Invalid status. Allowed values are: "
                    f"{', '.join(allowed_statuses)}"
                )
            }

        validated_data["status"] = appointment_status

    # -----------------------------------------------------
    # VALIDATE NOTES
    # -----------------------------------------------------

    if "notes" in data:

        notes = data.get("notes")

        if notes is not None and not isinstance(notes, str):
            return None, {
                "notes": "Notes must be a string or null."
            }

        if isinstance(notes, str):
            notes = notes.strip()

            if not notes:
                notes = None

        validated_data["notes"] = notes

    # -----------------------------------------------------
    # VALIDATE PHOTOS
    # -----------------------------------------------------

    if "photos" in data:

        photos = data.get("photos")

        if not isinstance(photos, list):
            return None, {
                "photos": "Photos must be provided as a list."
            }

        validated_photos = []

        for index, photo in enumerate(photos):

            if not isinstance(photo, dict):
                return None, {
                    "photos": f"Photo at position {index} must be an object."
                }

            allowed_photo_fields = {
                "image_path",
                "photo_type",
                "description"
            }

            unknown_photo_fields = (
                set(photo.keys()) - allowed_photo_fields
            )

            if unknown_photo_fields:
                return None, {
                    "photos": (
                        f"Unknown field(s) in photo at position {index}: "
                        f"{', '.join(unknown_photo_fields)}"
                    )
                }

            # Image path is mandatory.
            image_path = photo.get("image_path")

            if not isinstance(image_path, str) or not image_path.strip():
                return None, {
                    "photos": (
                        f"image_path is required for photo at position {index}."
                    )
                }

            image_path = image_path.strip()

            if len(image_path) > 500:
                return None, {
                    "photos": (
                        f"image_path at position {index} "
                        "cannot exceed 500 characters."
                    )
                }

            # Validate BEFORE / AFTER.
            photo_type = photo.get("photo_type")

            if not isinstance(photo_type, str):
                return None, {
                    "photos": (
                        f"photo_type is required for photo at position {index}."
                    )
                }

            photo_type = photo_type.strip().upper()

            if photo_type not in PatientPhoto.PhotoType.values:
                return None, {
                    "photos": (
                        f"Invalid photo_type at position {index}. "
                        "Allowed values are BEFORE and AFTER."
                    )
                }

            # Description is optional.
            description = photo.get("description")

            if description is not None and not isinstance(description, str):
                return None, {
                    "photos": (
                        f"description at position {index} "
                        "must be a string or null."
                    )
                }

            if isinstance(description, str):
                description = description.strip() or None

            validated_photos.append({
                "image_path": image_path,
                "photo_type": photo_type,
                "description": description
            })

        validated_data["photos"] = validated_photos

    return validated_data, None


# =========================================================
# HELPER 4: SAVE PHOTOS TO PATIENT VISIT
# =========================================================

def save_visit_photos(
    patient,
    visit,
    photos,
    username
):

    for photo_data in photos:

        image_path = photo_data["image_path"]
        photo_type = photo_data["photo_type"]

        # Avoid creating duplicate records when the same
        # Appointment PATCH request is submitted again.
        existing_photo = PatientPhoto.objects.filter(
            patient=patient,
            visit=visit,
            image_path=image_path,
            photo_type=photo_type
        ).first()

        if existing_photo:
            continue

        photo = PatientPhoto(
            patient=patient,
            visit=visit,
            image_path=image_path,
            photo_type=photo_type,
            description=photo_data["description"],
            created_by=username,
            updated_by=username
        )

        photo.full_clean()
        photo.save()


# =========================================================
# API 1: APPOINTMENT LIST AND CREATION
# =========================================================

class AppointmentListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # POST: CREATE APPOINTMENT
    # -----------------------------------------------------

    def post(self, request):

        validated_data, errors = validate_appointment_data(
            request.data,
            operation="create"
        )

        if errors:
            return CustomResponse.error(
                message="Validation failed.",
                errors=errors
            )

        patient_id = request.data.get("patient_id")

        try:
            patient = Patient.objects.get(
                id=patient_id,
                is_active=True
            )

        except (
            Patient.DoesNotExist,
            ValueError,
            TypeError,
            DjangoValidationError
        ):
            return CustomResponse.error(
                message="Active patient not found."
            )

        appointment = Appointment(
            patient=patient,
            appointment_datetime=validated_data["appointment_datetime"],
            status=Appointment.Status.SCHEDULED,
            created_by=request.user.username,
            updated_by=request.user.username
        )

        try:
            appointment.full_clean()
            appointment.save()

        except DjangoValidationError as error:
            return CustomResponse.error(
                message="Appointment validation failed.",
                errors=error.message_dict
            )

        return CustomResponse.success(
            message="Appointment created successfully.",
            data=appointment_data(appointment)
        )

    # -----------------------------------------------------
    # GET: LIST APPOINTMENTS
    # -----------------------------------------------------

    def get(self, request):

        appointments = Appointment.objects.select_related(
            "patient"
        ).prefetch_related(
            "visits__photos"
        ).all()

        current_datetime = timezone.now()

        # FILTER: UPCOMING / PREVIOUS

        appointment_type = request.query_params.get("type")

        if appointment_type:

            appointment_type = appointment_type.lower()

            if appointment_type == "upcoming":

                appointments = appointments.filter(
                    appointment_datetime__gte=current_datetime,
                    status=Appointment.Status.SCHEDULED
                )

            elif appointment_type == "previous":

                appointments = appointments.filter(
                    appointment_datetime__lt=current_datetime
                )

            else:
                return CustomResponse.error(
                    message="Invalid type. Use 'upcoming' or 'previous'."
                )

        # FILTER: STATUS

        appointment_status = request.query_params.get("status")

        if appointment_status:

            appointment_status = appointment_status.upper()

            if appointment_status not in Appointment.Status.values:
                return CustomResponse.error(
                    message="Invalid appointment status."
                )

            appointments = appointments.filter(
                status=appointment_status
            )

        # FILTER: PATIENT

        patient_id = request.query_params.get("patient_id")

        if patient_id:
            appointments = appointments.filter(
                patient_id=patient_id
            )

        appointments = appointments.order_by(
            "appointment_datetime"
        )

        # PAGINATION

        page = request.query_params.get("page", 1)
        size = request.query_params.get("size", 20)

        try:
            page = int(page)
            size = int(size)

            if page < 1 or size < 1:
                raise ValueError

        except (ValueError, TypeError):
            return CustomResponse.error(
                message="Page and size must be positive integers."
            )

        paginator = Paginator(appointments, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:
            return CustomResponse.error(
                message="Requested page does not exist."
            )

        appointment_list = [
            appointment_data(appointment)
            for appointment in page_obj
        ]

        return CustomResponse.success(
            message="Appointments retrieved successfully.",
            data={
                "pagination": {
                    "total_records": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "page_size": size,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous()
                },
                "results": appointment_list
            }
        )


# =========================================================
# API 2: APPOINTMENT RETRIEVAL AND UPDATION
# =========================================================

class AppointmentDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # HELPER: GET APPOINTMENT
    # -----------------------------------------------------

    def get_appointment(self, appointment_id):

        try:
            return Appointment.objects.select_related(
                "patient"
            ).prefetch_related(
                "visits__photos"
            ).get(id=appointment_id)

        except (Appointment.DoesNotExist, ValueError, TypeError):
            return None

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def get(self, request, appointment_id):

        appointment = self.get_appointment(appointment_id)

        if appointment is None:
            return CustomResponse.error(
                message="Appointment not found."
            )

        return CustomResponse.success(
            message="Appointment retrieved successfully.",
            data=appointment_data(appointment)
        )

    # -----------------------------------------------------
    # PUT
    # -----------------------------------------------------

    def put(self, request, appointment_id):

        return self.update_appointment(
            request,
            appointment_id,
            partial=False
        )

    # -----------------------------------------------------
    # PATCH
    # -----------------------------------------------------

    def patch(self, request, appointment_id):

        return self.update_appointment(
            request,
            appointment_id,
            partial=True
        )

    # -----------------------------------------------------
    # COMMON UPDATE LOGIC
    # -----------------------------------------------------


    def update_appointment(self, request, appointment_id, partial):

        try:

            with transaction.atomic():

                # -------------------------------------------------
                # GET AND LOCK APPOINTMENT
                # -------------------------------------------------

                try:
                    appointment = Appointment.objects.select_for_update().select_related(
                        "patient"
                    ).get(id=appointment_id)

                except (
                    Appointment.DoesNotExist,
                    ValueError,
                    TypeError
                ):
                    raise TransactionValidationError(
                        message="Appointment not found."
                    )

                # -------------------------------------------------
                # VALIDATE REQUEST DATA
                # -------------------------------------------------

                validated_data, errors = validate_appointment_data(
                    request.data,
                    operation="update",
                    partial=partial
                )

                if errors:
                    raise TransactionValidationError(
                        message="Validation failed."
                    )

                # Keep photos separate from Appointment model fields.
                photos_provided = "photos" in validated_data
                photos_data = validated_data.pop("photos", [])

                resulting_status = validated_data.get(
                    "status",
                    appointment.status
                )

                # -------------------------------------------------
                # VALIDATE NOTES
                # -------------------------------------------------

                if (
                    "notes" in validated_data
                    and resulting_status != Appointment.Status.COMPLETED
                ):
                    raise TransactionValidationError(
                        message=(
                            "Consultation or treatment notes can only be "
                            "added or updated after the appointment is completed."
                        )
                    )

                # -------------------------------------------------
                # VALIDATE PHOTOS
                # -------------------------------------------------

                if (
                    photos_provided
                    and resulting_status != Appointment.Status.COMPLETED
                ):
                    raise TransactionValidationError(
                        message=(
                            "Photos can only be added after the appointment "
                            "is marked as completed."
                        )
                    )

                # -------------------------------------------------
                # UPDATE APPOINTMENT
                # -------------------------------------------------

                for field, value in validated_data.items():
                    setattr(appointment, field, value)

                appointment.updated_by = request.user.username

                try:
                    appointment.full_clean()
                    appointment.save()

                except DjangoValidationError as error:
                    raise TransactionValidationError(
                        message="Appointment validation failed."
                    )

                # -------------------------------------------------
                # CREATE OR UPDATE PATIENT VISIT
                # -------------------------------------------------

                if appointment.status == Appointment.Status.COMPLETED:

                    visit = PatientVisit.objects.filter(
                        appointment=appointment
                    ).order_by("-visit_date").first()

                    if visit is None:

                        visit = PatientVisit(
                            patient=appointment.patient,
                            appointment=appointment,
                            visit_date=appointment.appointment_datetime,
                            consultant_name=CONSULTANT_NAME,
                            notes=appointment.notes,
                            created_by=request.user.username,
                            updated_by=request.user.username
                        )

                    else:

                        visit.visit_date = appointment.appointment_datetime
                        visit.consultant_name = CONSULTANT_NAME
                        visit.notes = appointment.notes
                        visit.updated_by = request.user.username

                    try:
                        visit.full_clean()
                        visit.save()

                    except DjangoValidationError as error:
                        raise TransactionValidationError(
                            message="Patient visit validation failed."
                        )

                    # -------------------------------------------------
                    # SAVE PHOTOS AGAINST THE PATIENT VISIT
                    # -------------------------------------------------

                    if photos_provided and photos_data:

                        try:
                            save_visit_photos(
                                patient=appointment.patient,
                                visit=visit,
                                photos=photos_data,
                                username=request.user.username
                            )

                        except DjangoValidationError as error:
                            raise TransactionValidationError(
                                message="Photo validation failed."
                            )

            # The transaction commits successfully here.

        except TransactionValidationError as error:

            # Any exception raised inside transaction.atomic()
            # causes all database changes in that transaction
            # to be rolled back.

            if error.errors:
                return CustomResponse.error(
                    message=error.message
                )

            return CustomResponse.error(
                message=error.message
            )

        # -----------------------------------------------------
        # REFRESH APPOINTMENT AFTER SUCCESSFUL TRANSACTION
        # -----------------------------------------------------

        appointment = self.get_appointment(appointment_id)

        return CustomResponse.success(
            message="Appointment updated successfully.",
            data=appointment_data(appointment)
        )



# =========================================================
# API 3: PATIENT'S NEXT SCHEDULED APPOINTMENT
# =========================================================

class PatientNextAppointmentAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):

        try:
            patient = Patient.objects.get(id=patient_id)

        except (Patient.DoesNotExist, ValueError, TypeError):
            return CustomResponse.error(
                message="Patient not found."
            )

        next_appointment = Appointment.objects.select_related(
            "patient"
        ).prefetch_related(
            "visits__photos"
        ).filter(
            patient=patient,
            status=Appointment.Status.SCHEDULED,
            appointment_datetime__gte=timezone.now()
        ).order_by(
            "appointment_datetime"
        ).first()

        if next_appointment is None:
            return CustomResponse.success(
                message="No upcoming scheduled appointment found.",
                data=None
            )

        return CustomResponse.success(
            message="Next appointment retrieved successfully.",
            data=appointment_data(next_appointment)
        )
