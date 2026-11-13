
# =========================================================
# IMPORTS
# =========================================================

# Django utilities for pagination.
from django.core.paginator import Paginator, EmptyPage

# Django utilities for date and time handling.
from django.utils import timezone
from django.utils.dateparse import parse_datetime

# Django model validation exception.
from django.core.exceptions import ValidationError as DjangoValidationError

# DRF classes for APIs, authentication and responses.
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# Import database models.
from db.models.appointment import Appointment
from db.models.patient import Patient


# =========================================================
# HELPER FUNCTION 1: FORMAT APPOINTMENT RESPONSE
# =========================================================
# Converts an Appointment object into a dictionary.
# Used by create, retrieve and update APIs.

def appointment_data(appointment):

    return {
        "id": str(appointment.id),

        # Patient details linked to this appointment.
        "patient": {
            "id": str(appointment.patient.id),
            "full_name": appointment.patient.full_name,
            "mobile": appointment.patient.mobile
        },

        # Appointment date and time.
        "appointment_datetime": appointment.appointment_datetime.isoformat(),

        # Consultation or treatment notes.
        # This will be null if no notes have been added.
        "notes": appointment.notes,

        # Current appointment status.
        "status": appointment.status,

        # Audit information.
        "created_at": appointment.created_at,
        "updated_at": appointment.updated_at,
        "created_by": appointment.created_by,
        "updated_by": appointment.updated_by
    }


# =========================================================
# HELPER FUNCTION 2: VALIDATE APPOINTMENT DATA
# =========================================================
# operation="create" for POST.
# operation="update" for PUT and PATCH.
# partial=True for PATCH requests.

def validate_appointment_data(data, operation="create", partial=False):

    # Fields accepted while creating an appointment.
    create_fields = {
        "patient_id",
        "appointment_datetime"
    }

    # Fields accepted while updating an appointment.
    # Patient ID cannot be changed after creation.
    update_fields = {
        "appointment_datetime",
        "status",
        "notes"
    }

    # Select allowed fields based on the operation.
    allowed_fields = (
        create_fields if operation == "create"
        else update_fields
    )

    # Reject fields that are not supported.
    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        return None, {
            "error": f"Unknown field(s): {', '.join(unknown_fields)}"
        }

    # During creation, patient ID and appointment date/time are mandatory.
    if operation == "create":

        missing_fields = create_fields - set(data.keys())

        if missing_fields:
            return None, {
                "error": f"Missing field(s): {', '.join(missing_fields)}"
            }

    elif not partial:

        # PUT requires appointment date/time and status.
        # Notes remain optional.
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

        # PATCH must contain at least one field.
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

        # Convert ISO 8601 string into a Python datetime object.
        appointment_datetime = parse_datetime(date_time_value.strip())

        if appointment_datetime is None:
            return None, {
                "appointment_datetime": (
                    "Enter a valid ISO 8601 date-time. "
                    "Example: 2026-11-20T10:30:00+05:30"
                )
            }

        # Apply the current Django timezone if no timezone was provided.
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

        # Get valid status values from the Appointment model.
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
    # VALIDATE CONSULTATION / TREATMENT NOTES
    # -----------------------------------------------------

    if "notes" in data:

        notes = data.get("notes")

        # Notes can be a string or null.
        if notes is not None and not isinstance(notes, str):
            return None, {
                "notes": "Notes must be a string or null."
            }

        # Convert empty or whitespace-only notes into None.
        if isinstance(notes, str):
            notes = notes.strip()
            if not notes:
                notes = None

        validated_data["notes"] = notes

    return validated_data, None


# =========================================================
# API 1: APPOINTMENT LIST AND CREATION
# =========================================================
#
# POST /backoffice/appointments/
#     -> Create a new appointment.
#
# GET  /backoffice/appointments/
#     -> Retrieve appointments with pagination and filters.

class AppointmentListCreateAPIView(APIView):

    # Only authenticated clinic staff can access this API.
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # POST: CREATE A NEW APPOINTMENT
    # -----------------------------------------------------

    def post(self, request):

        # Validate appointment creation data.
        validated_data, errors = validate_appointment_data(
            request.data,
            operation="create"
        )

        if errors:
            return Response(
                errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Retrieve the patient ID from the request.
        patient_id = request.data.get("patient_id")

        # Check whether the patient exists and is active.
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
            return Response(
                {"error": "Active patient not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Create the appointment.
        # New appointments always start with SCHEDULED status.
        # Notes are added after completion, not during creation.
        appointment = Appointment(
            patient=patient,
            appointment_datetime=validated_data["appointment_datetime"],
            status=Appointment.Status.SCHEDULED,
            created_by=request.user.username,
            updated_by=request.user.username
        )

        # Validate model fields before saving.
        try:
            appointment.full_clean()

        except DjangoValidationError as e:
            return Response(
                {"error": e.message_dict},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save the appointment in the database.
        appointment.save()

        return Response(
            {
                "message": "Appointment created successfully.",
                "data": appointment_data(appointment)
            },
            status=status.HTTP_201_CREATED
        )

    # -----------------------------------------------------
    # GET: RETRIEVE APPOINTMENTS WITH PAGINATION
    # -----------------------------------------------------

    def get(self, request):

        # Retrieve appointments along with their patient details.
        appointments = Appointment.objects.select_related(
            "patient"
        ).all()

        current_datetime = timezone.now()

        # -------------------------------------------------
        # FILTER 1: UPCOMING OR PREVIOUS APPOINTMENTS
        # -------------------------------------------------

        appointment_type = request.query_params.get("type")

        if appointment_type:

            appointment_type = appointment_type.lower()

            if appointment_type == "upcoming":

                # Future appointments that are still scheduled.
                appointments = appointments.filter(
                    appointment_datetime__gte=current_datetime,
                    status=Appointment.Status.SCHEDULED
                )

            elif appointment_type == "previous":

                # Appointments whose date/time has passed.
                appointments = appointments.filter(
                    appointment_datetime__lt=current_datetime
                )

            else:
                return Response(
                    {
                        "error": (
                            "Invalid type. Use 'upcoming' or 'previous'."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # -------------------------------------------------
        # FILTER 2: APPOINTMENT STATUS
        # -------------------------------------------------

        appointment_status = request.query_params.get("status")

        if appointment_status:

            appointment_status = appointment_status.upper()

            if appointment_status not in Appointment.Status.values:
                return Response(
                    {"error": "Invalid appointment status."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            appointments = appointments.filter(
                status=appointment_status
            )

        # -------------------------------------------------
        # FILTER 3: PATIENT ID
        # -------------------------------------------------

        patient_id = request.query_params.get("patient_id")

        if patient_id:
            appointments = appointments.filter(
                patient_id=patient_id
            )

        # Sort appointments by date and time.
        appointments = appointments.order_by(
            "appointment_datetime"
        )

        # -------------------------------------------------
        # PAGINATION
        # -------------------------------------------------

        page = request.query_params.get("page", 1)
        size = request.query_params.get("size", 20)

        # Validate page and size values.
        try:
            page = int(page)
            size = int(size)

            if page < 1 or size < 1:
                raise ValueError

        except (ValueError, TypeError):
            return Response(
                {"error": "Page and size must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Divide the filtered appointments into pages.
        paginator = Paginator(appointments, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:
            return Response(
                {"error": "Requested page does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Convert appointments into response dictionaries.
        appointment_list = [
            appointment_data(appointment)
            for appointment in page_obj
        ]

        return Response(
            {
                "message": "Appointments retrieved successfully.",
                "pagination": {
                    "total_records": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "page_size": size,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous()
                },
                "data": appointment_list
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# API 2: APPOINTMENT RETRIEVAL AND UPDATION
# =========================================================
#
# GET   /backoffice/appointments/<appointment_id>/
#       -> Retrieve one appointment.
#
# PUT   /backoffice/appointments/<appointment_id>/
#       -> Update appointment date/time and status.
#
# PATCH /backoffice/appointments/<appointment_id>/
#       -> Update selected fields, including notes.

class AppointmentDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # HELPER: RETRIEVE APPOINTMENT USING UUID
    # -----------------------------------------------------

    def get_appointment(self, appointment_id):

        try:
            return Appointment.objects.select_related(
                "patient"
            ).get(id=appointment_id)

        except (Appointment.DoesNotExist, ValueError, TypeError):
            return None

    # -----------------------------------------------------
    # GET: RETRIEVE ONE APPOINTMENT
    # -----------------------------------------------------

    def get(self, request, appointment_id):

        appointment = self.get_appointment(appointment_id)

        if appointment is None:
            return Response(
                {"error": "Appointment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "message": "Appointment retrieved successfully.",
                "data": appointment_data(appointment)
            },
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # PUT: UPDATE APPOINTMENT
    # -----------------------------------------------------

    def put(self, request, appointment_id):

        return self.update_appointment(
            request,
            appointment_id,
            partial=False
        )

    # -----------------------------------------------------
    # PATCH: PARTIAL APPOINTMENT UPDATE
    # -----------------------------------------------------

    def patch(self, request, appointment_id):

        return self.update_appointment(
            request,
            appointment_id,
            partial=True
        )

    # -----------------------------------------------------
    # HELPER: COMMON UPDATE LOGIC
    # -----------------------------------------------------

    def update_appointment(self, request, appointment_id, partial):

        # Find the appointment.
        appointment = self.get_appointment(appointment_id)

        if appointment is None:
            return Response(
                {"error": "Appointment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate the update request.
        validated_data, errors = validate_appointment_data(
            request.data,
            operation="update",
            partial=partial
        )

        if errors:
            return Response(
                errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determine the status after applying this update.
        # This also supports completing an appointment and
        # adding notes in the same PATCH request.
        resulting_status = validated_data.get(
            "status",
            appointment.status
        )

        # Notes can only be added or changed after completion.
        if (
            "notes" in validated_data
            and resulting_status != Appointment.Status.COMPLETED
        ):
            return Response(
                {
                    "error": (
                        "Consultation or treatment notes can only be "
                        "added or updated after the appointment is completed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Apply the validated fields to the appointment.
        # Patient relationship is intentionally not editable.
        for field, value in validated_data.items():
            setattr(appointment, field, value)

        # Record the staff member who updated the appointment.
        appointment.updated_by = request.user.username

        # Validate the updated model before saving.
        try:
            appointment.full_clean()

        except DjangoValidationError as e:
            return Response(
                {"error": e.message_dict},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save changes in the database.
        appointment.save()

        return Response(
            {
                "message": "Appointment updated successfully.",
                "data": appointment_data(appointment)
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# API 3: PATIENT'S NEXT SCHEDULED APPOINTMENT
# =========================================================
#
# GET /backoffice/patients/<patient_id>/next-appointment/
#
# Retrieves the nearest future appointment whose status
# is SCHEDULED for the specified patient.

class PatientNextAppointmentAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):

        # Check whether the patient exists.
        try:
            patient = Patient.objects.get(id=patient_id)

        except (Patient.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": "Patient not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Find the nearest future scheduled appointment.
        next_appointment = Appointment.objects.select_related(
            "patient"
        ).filter(
            patient=patient,
            status=Appointment.Status.SCHEDULED,
            appointment_datetime__gte=timezone.now()
        ).order_by(
            "appointment_datetime"
        ).first()

        # Return null when no upcoming appointment exists.
        if next_appointment is None:
            return Response(
                {
                    "message": "No upcoming scheduled appointment found.",
                    "data": None
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "message": "Next appointment retrieved successfully.",
                "data": appointment_data(next_appointment)
            },
            status=status.HTTP_200_OK
        )
