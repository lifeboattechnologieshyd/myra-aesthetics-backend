
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from db.models.patient import Patient
from db.models.appointment import Appointment
from db.models.patient_visit import PatientVisit
from db.models.patient_photo import PatientPhoto

from shared.utils.custom_response import CustomResponse


# =========================================================
# HELPER 1: FORMAT PATIENT PROFILE
# =========================================================

def patient_history_profile(patient):

    return {
        "id": str(patient.id),
        "full_name": patient.full_name,
        "gender": patient.gender,
        "mobile": patient.mobile,
        "alternate_mobile": patient.alternate_mobile,
        "email": patient.email,
        "date_of_birth": (
            patient.date_of_birth.isoformat()
            if patient.date_of_birth else None
        ),
        "address": patient.address,
        "is_active": patient.is_active,
    }


# =========================================================
# HELPER 2: FORMAT PATIENT VISIT WITH PHOTOS
# =========================================================

def history_visit_data(visit):

    before_photos = []
    after_photos = []

    for photo in visit.photos.all():

        photo_data = {
            "id": str(photo.id),
            "image_path": photo.image_path,
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
        "appointment_id": (
            str(visit.appointment_id)
            if visit.appointment_id else None
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
    }


# =========================================================
# HELPER 3: FORMAT APPOINTMENT
# =========================================================

def history_appointment_data(appointment):

    return {
        "id": str(appointment.id),
        "patient_id": str(appointment.patient_id),
        "patient_name": appointment.patient.full_name,
        "appointment_datetime": (
            appointment.appointment_datetime.isoformat()
        ),
        "notes": appointment.notes,
        "status": appointment.status,
        "created_at": appointment.created_at.isoformat(),
        "updated_at": appointment.updated_at.isoformat(),
    }


# =========================================================
# API: COMPLETE PATIENT HISTORY
# =========================================================
#
# GET /backoffice/patients/<patient_id>/history/
#
# Returns:
# 1. Patient profile
# 2. Patient visit history with before/after photos
# 3. Previous appointments
# 4. Upcoming scheduled appointments


class PatientHistoryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):

        # -------------------------------------------------
        # STEP 1: RETRIEVE PATIENT
        # -------------------------------------------------

        try:
            patient = Patient.objects.get(id=patient_id)

        except (Patient.DoesNotExist, ValueError, TypeError):
            return CustomResponse.error(
                message="Patient not found."
            )

        current_datetime = timezone.now()

        # -------------------------------------------------
        # STEP 2: RETRIEVE PATIENT VISITS
        # -------------------------------------------------

        visits = PatientVisit.objects.filter(
            patient=patient
        ).select_related(
            "patient",
            "appointment"
        ).prefetch_related(
            "photos"
        ).order_by(
            "-visit_date"
        )

        visit_list = [
            history_visit_data(visit)
            for visit in visits
        ]

        # -------------------------------------------------
        # STEP 3: RETRIEVE PREVIOUS APPOINTMENTS
        # -------------------------------------------------

        previous_appointments = Appointment.objects.filter(
            patient=patient,
            appointment_datetime__lt=current_datetime
        ).select_related(
            "patient"
        ).order_by(
            "-appointment_datetime"
        )

        previous_appointment_list = [
            history_appointment_data(appointment)
            for appointment in previous_appointments
        ]

        # -------------------------------------------------
        # STEP 4: RETRIEVE UPCOMING APPOINTMENTS
        # -------------------------------------------------

        upcoming_appointments = Appointment.objects.filter(
            patient=patient,
            status=Appointment.Status.SCHEDULED,
            appointment_datetime__gte=current_datetime
        ).select_related(
            "patient"
        ).order_by(
            "appointment_datetime"
        )

        upcoming_appointment_list = [
            history_appointment_data(appointment)
            for appointment in upcoming_appointments
        ]

        # -------------------------------------------------
        # STEP 5: PREPARE COMPLETE PATIENT HISTORY
        # -------------------------------------------------

        history_data = {
            "patient": patient_history_profile(patient),

            "visit_history": {
                "total_visits": len(visit_list),
                "results": visit_list,
            },

            "previous_appointments": {
                "total_appointments": len(
                    previous_appointment_list
                ),
                "results": previous_appointment_list,
            },

            "upcoming_appointments": {
                "total_appointments": len(
                    upcoming_appointment_list
                ),
                "results": upcoming_appointment_list,
            },
        }

        return CustomResponse.success(
            message="Patient history retrieved successfully.",
            data=history_data
        )
