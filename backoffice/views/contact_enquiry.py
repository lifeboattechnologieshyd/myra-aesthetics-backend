
from django.core.paginator import Paginator, EmptyPage
from django.utils.dateparse import parse_date

from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from db.models import ContactEnquiry
from shared.utils.custom_response import CustomResponse


# COMMON CONTACT ENQUIRY RESPONSE
def contact_enquiry_data(enquiry):

    return {
        "enquiry_id": str(enquiry.id),
        "fullName": enquiry.full_name,
        "phone": enquiry.phone,
        "email": enquiry.email,
        "treatment": enquiry.treatment,
        "doctor": enquiry.doctor,
        "preferredDate": enquiry.preferred_date.isoformat(),
        "preferredTime": enquiry.preferred_time,
        "message": enquiry.message,
        "permission": enquiry.permission,
        "source": enquiry.source,
        "created_at": enquiry.created_at.isoformat(),
        "updated_at": enquiry.updated_at.isoformat()
    }


# =========================================================
# API 1: CONTACT ENQUIRY LIST
# =========================================================
#
# GET /backoffice/contact-enquiries/
#
# Retrieves enquiries with search, filters and pagination.


class ContactEnquiryListAPIView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request):

        enquiries = ContactEnquiry.objects.all().order_by("-created_at")

        # SEARCH BY NAME, PHONE OR EMAIL
        search = request.query_params.get("search")

        if search:
            enquiries = enquiries.filter(
                models.Q(full_name__icontains=search)
                | models.Q(phone__icontains=search)
                | models.Q(email__icontains=search)
            )

        # FILTER BY TREATMENT
        treatment = request.query_params.get("treatment")

        if treatment:
            enquiries = enquiries.filter(
                treatment__icontains=treatment.strip()
            )

        # FILTER BY ENQUIRY CREATION DATE
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        parsed_start = None
        parsed_end = None

        if start_date:
            parsed_start = parse_date(start_date)

            if parsed_start is None:
                return CustomResponse.error(
                    message="Invalid start_date. Use YYYY-MM-DD."
                )

            enquiries = enquiries.filter(
                created_at__date__gte=parsed_start
            )

        if end_date:
            parsed_end = parse_date(end_date)

            if parsed_end is None:
                return CustomResponse.error(
                    message="Invalid end_date. Use YYYY-MM-DD."
                )

            enquiries = enquiries.filter(
                created_at__date__lte=parsed_end
            )

        if (
            parsed_start
            and parsed_end
            and parsed_start > parsed_end
        ):
            return CustomResponse.error(
                message="start_date cannot be after end_date."
            )

        # PAGINATION
        try:
            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("size", 20))

            if page < 1 or size < 1 or size > 100:
                raise ValueError

        except (ValueError, TypeError):
            return CustomResponse.error(
                message="Page must be positive and size must be between 1 and 100."
            )

        paginator = Paginator(enquiries, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:
            return CustomResponse.error(
                message="Requested page does not exist."
            )

        enquiry_list = [
            contact_enquiry_data(enquiry)
            for enquiry in page_obj
        ]

        return CustomResponse.success(
            message="Contact enquiries retrieved successfully.",
            data={
                "pagination": {
                    "total_records": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "page_size": size,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous()
                },
                "results": enquiry_list
            }
        )


# =========================================================
# API 2: CONTACT ENQUIRY DETAILS
# =========================================================
#
# GET /backoffice/contact-enquiries/<enquiry_id>/
#
# Retrieves one enquiry.


class ContactEnquiryDetailAPIView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request, enquiry_id):

        try:
            enquiry = ContactEnquiry.objects.get(id=enquiry_id)

        except (
            ContactEnquiry.DoesNotExist,
            ValueError,
            TypeError
        ):
            return CustomResponse.error(
                message="Contact enquiry not found."
            )

        return CustomResponse.success(
            message="Contact enquiry retrieved successfully.",
            data=contact_enquiry_data(enquiry)
        )
