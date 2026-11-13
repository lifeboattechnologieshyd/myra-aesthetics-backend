from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from db.models import Patient


# Fields accepted from the API
PATIENT_FIELDS = {
    "full_name",
    "gender",
    "mobile",
    "alternate_mobile",
    "email",
    "date_of_birth",
    "address",
}

REQUIRED_FIELDS = {
    "full_name",
    "gender",
    "mobile",
}

OPTIONAL_FIELDS = {
    "alternate_mobile",
    "email",
    "date_of_birth",
    "address",
}


def patient_data(patient):
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
        "created_at": patient.created_at.isoformat(),
        "updated_at": patient.updated_at.isoformat(),
        "created_by": patient.created_by,
        "updated_by": patient.updated_by,
    }


def validate_patient_data(data, partial=False):
    """
    Validate incoming patient fields and return cleaned values.
    """

    unknown_fields = set(data.keys()) - PATIENT_FIELDS

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

    for field in PATIENT_FIELDS:

        if field not in data:
            if not partial and field in OPTIONAL_FIELDS:
                values[field] = None
            continue

        value = data[field]

        # Normalize optional empty values to None
        if field in OPTIONAL_FIELDS and value == "":
            value = None

        # Validate text fields
        if field in {
            "full_name",
            "gender",
            "mobile",
            "alternate_mobile",
            "email",
            "address",
        }:
            if value is not None and not isinstance(value, str):
                raise ValueError(
                    f"{field} must be a string."
                )

            if isinstance(value, str):
                value = value.strip()

        # Validate mandatory fields
        if field in REQUIRED_FIELDS:
            if not value:
                raise ValueError(
                    f"{field} is required."
                )

        # Normalize gender
        if field == "gender" and isinstance(value, str):
            value = value.upper()

        # Optional fields should not contain empty strings
        if field in OPTIONAL_FIELDS and value == "":
            value = None

        values[field] = value

    return values


def model_validation_errors(patient):
    try:
        patient.full_clean()
        return None

    except DjangoValidationError as error:
        return error.message_dict


class PatientListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # CREATE PATIENT
    def post(self, request, format=None):

        try:
            values = validate_patient_data(request.data)

            username = request.user.username

            patient = Patient(
                **values,
                created_by=username,
                updated_by=username
            )

            errors = model_validation_errors(patient)

            if errors:
                return Response(
                    {"errors": errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            patient.save()

            return Response(
                {
                    "message": "Patient created successfully.",
                    "patient": patient_data(patient)
                },
                status=status.HTTP_201_CREATED
            )

        except ValueError as error:
            return Response(
                {"message": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

    # RETRIEVE ALL PATIENTS
    def get(self, request, format=None):

        queryset = Patient.objects.all().order_by(
            "-created_at", "-id"
        )

        # SEARCH BY NAME OR CONTACT NUMBER
        search = request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search.strip()) |
                Q(mobile__icontains=search.strip()) |
                Q(alternate_mobile__icontains=search.strip())
            )

        # FILTER BY GENDER
        gender = request.query_params.get("gender")

        if gender:
            gender = gender.upper()

            valid_genders = Patient.Gender.values

            if gender not in valid_genders:
                return Response(
                    {"message": "Invalid gender filter."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            queryset = queryset.filter(gender=gender)

        # FILTER BY ACTIVE STATUS
        is_active = request.query_params.get("is_active")

        if is_active is not None:

            if is_active.lower() not in ["true", "false"]:
                return Response(
                    {"message": "is_active must be true or false."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            queryset = queryset.filter(
                is_active=(is_active.lower() == "true")
            )

        # PAGINATION
        try:
            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("size", 20))

            if page < 1:
                raise ValueError("Page must be at least 1.")

            if size < 1 or size > 100:
                raise ValueError(
                    "Size must be between 1 and 100."
                )

        except (ValueError, TypeError):
            return Response(
                {
                    "message": (
                        "Invalid pagination values. "
                        "Page must be a positive integer and "
                        "size must be between 1 and 100."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        paginator = Paginator(queryset, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:
            return Response(
                {"message": "Requested page does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        results = [
            patient_data(patient)
            for patient in page_obj
        ]

        return Response(
            {
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page,
                "page_size": size,
                "results": results
            },
            status=status.HTTP_200_OK
        )


class PatientDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get_patient(self, patient_id):

        try:
            return Patient.objects.get(id=patient_id)

        except Patient.DoesNotExist:
            return None

    # RETRIEVE ONE PATIENT
    def get(self, request, patient_id, format=None):

        patient = self.get_patient(patient_id)

        if patient is None:
            return Response(
                {"message": "Patient not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "patient": patient_data(patient)
            },
            status=status.HTTP_200_OK
        )

    # UPDATE COMPLETE PATIENT PROFILE
    def put(self, request, patient_id, format=None):

        patient = self.get_patient(patient_id)

        if patient is None:
            return Response(
                {"message": "Patient not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            values = validate_patient_data(request.data)

            for field, value in values.items():
                setattr(patient, field, value)

            patient.updated_by = request.user.username

            errors = model_validation_errors(patient)

            if errors:
                return Response(
                    {"errors": errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            patient.save()

            return Response(
                {
                    "message": "Patient updated successfully.",
                    "patient": patient_data(patient)
                },
                status=status.HTTP_200_OK
            )

        except ValueError as error:
            return Response(
                {"message": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

    # PARTIALLY UPDATE PATIENT PROFILE
    def patch(self, request, patient_id, format=None):

        patient = self.get_patient(patient_id)

        if patient is None:
            return Response(
                {"message": "Patient not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not request.data:
            return Response(
                {"message": "At least one field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            values = validate_patient_data(
                request.data,
                partial=True
            )

            for field, value in values.items():
                setattr(patient, field, value)

            patient.updated_by = request.user.username

            errors = model_validation_errors(patient)

            if errors:
                return Response(
                    {"errors": errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            patient.save()

            return Response(
                {
                    "message": "Patient updated successfully.",
                    "patient": patient_data(patient)
                },
                status=status.HTTP_200_OK
            )

        except ValueError as error:
            return Response(
                {"message": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

    # SOFT DELETE PATIENT
    def delete(self, request, patient_id, format=None):

        # Find the patient
        patient = Patient.objects.filter(id=patient_id).first()

        if not patient:
            return Response(
                {"message": "Patient not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check whether the patient is already inactive
        if not patient.is_active:
            return Response(
                {"message": "Patient profile is already inactive"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark patient as inactive instead of permanently deleting the profile
        patient.is_active = False
        patient.updated_by = request.user.username
        patient.save()

        return Response(
            {"message": "Patient profile deactivated successfully"},
            status=status.HTTP_200_OK
        )