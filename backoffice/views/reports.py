
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.core.paginator import Paginator, EmptyPage
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from db.models import (
    Patient,
    PatientVisit,
    Appointment,
    Invoice,
    InvoiceItem,
    InvoicePayment
)

from shared.utils.custom_response import CustomResponse


# --------------------------------------------------
# COMMON HELPERS
# --------------------------------------------------

ZERO = Decimal("0.00")


def get_date_range(request):

    start_value = request.query_params.get("start_date")
    end_value = request.query_params.get("end_date")

    if bool(start_value) != bool(end_value):
        return None, None, "Both start_date and end_date are required."

    if not start_value:
        return None, None, None

    start_date = parse_date(start_value)
    end_date = parse_date(end_value)

    if not start_date or not end_date:
        return None, None, "Invalid date format. Use YYYY-MM-DD."

    if start_date > end_date:
        return None, None, "start_date cannot be after end_date."

    return start_date, end_date, None


def apply_date_filter(queryset, field, start_date, end_date):

    if start_date and end_date:
        return queryset.filter(
            **{
                f"{field}__date__range": (start_date, end_date)
            }
        )

    return queryset


def get_grouping(request):

    group_by = request.query_params.get("group_by", "daily")

    if group_by not in ["daily", "monthly"]:
        return None

    return group_by


def get_period_expression(group_by, field):

    if group_by == "daily":
        return TruncDate(field)

    return TruncMonth(field)


def format_period(value, group_by):

    if group_by == "daily":
        return value.strftime("%Y-%m-%d")

    return value.strftime("%Y-%m")


def paginate_data(request, queryset, serializer_function):

    try:
        page = int(request.query_params.get("page", 1))
        size = int(request.query_params.get("size", 10))

        if page < 1 or size < 1 or size > 100:
            raise ValueError

    except (ValueError, TypeError):
        return None, "Invalid pagination parameters."

    paginator = Paginator(queryset, size)

    try:
        page_obj = paginator.page(page)

    except EmptyPage:
        return None, "Page number does not exist."

    return {
        "count": paginator.count,
        "total_pages": paginator.num_pages,
        "current_page": page,
        "page_size": size,
        "results": [
            serializer_function(obj)
            for obj in page_obj.object_list
        ]
    }, None


# --------------------------------------------------
# DATA FORMATTERS
# --------------------------------------------------

def appointment_data(appointment):

    return {
        "id": str(appointment.id),
        "patient_id": str(appointment.patient_id),
        "patient_name": appointment.patient.full_name,
        "mobile": appointment.patient.mobile,
        "appointment_datetime": appointment.appointment_datetime,
        "status": appointment.status,
        "notes": appointment.notes
    }


def patient_visit_data(visit):

    return {
        "id": str(visit.id),
        "patient_id": str(visit.patient_id),
        "patient_name": visit.patient.full_name,
        "appointment_id": (
            str(visit.appointment_id)
            if visit.appointment_id else None
        ),
        "visit_date": visit.visit_date,
        "notes": visit.notes
    }


# --------------------------------------------------
# 1. PATIENT REGISTRATION REPORT
# --------------------------------------------------

class PatientRegistrationReportAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        start_date, end_date, error = get_date_range(request)

        if error:
            return CustomResponse.error(message=error)

        patients = Patient.objects.all()

        patients = apply_date_filter(
            patients,
            "created_at",
            start_date,
            end_date
        )

        return CustomResponse.success(
            message="Patient registration report retrieved successfully.",
            data={
                "total_patients": patients.count(),
                "active_patients": patients.filter(is_active=True).count(),
                "inactive_patients": patients.filter(is_active=False).count(),
                "start_date": start_date,
                "end_date": end_date
            }
        )


# --------------------------------------------------
# 2. PATIENT VISIT REPORT
# --------------------------------------------------

class PatientVisitReportAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        start_date, end_date, error = get_date_range(request)

        if error:
            return CustomResponse.error(message=error)

        group_by = get_grouping(request)

        if not group_by:
            return CustomResponse.error(
                message="Invalid group_by. Use daily or monthly."
            )

        visits = PatientVisit.objects.all()

        visits = apply_date_filter(
            visits,
            "visit_date",
            start_date,
            end_date
        )

        period_expression = get_period_expression(
            group_by,
            "visit_date"
        )

        summary = (
            visits
            .annotate(report_period=period_expression)
            .values("report_period")
            .annotate(total_visits=Count("id"))
            .order_by("report_period")
        )

        summary_data = [
            {
                "period": format_period(
                    row["report_period"],
                    group_by
                ),
                "total_visits": row["total_visits"]
            }
            for row in summary
        ]

        return CustomResponse.success(
            message="Patient visit report retrieved successfully.",
            data={
                "total_visits": visits.count(),
                "group_by": group_by,
                "start_date": start_date,
                "end_date": end_date,
                "summary": summary_data
            }
        )


# --------------------------------------------------
# 3. APPOINTMENT STATUS SUMMARY
# --------------------------------------------------

class AppointmentSummaryReportAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        start_date, end_date, error = get_date_range(request)

        if error:
            return CustomResponse.error(message=error)

        appointments = Appointment.objects.all()

        appointments = apply_date_filter(
            appointments,
            "appointment_datetime",
            start_date,
            end_date
        )

        now = timezone.now()

        return CustomResponse.success(
            message="Appointment summary retrieved successfully.",
            data={
                "total_appointments": appointments.count(),

                "scheduled": appointments.filter(
                    status=Appointment.Status.SCHEDULED
                ).count(),

                "upcoming": appointments.filter(
                    status=Appointment.Status.SCHEDULED,
                    appointment_datetime__gte=now
                ).count(),

                "completed": appointments.filter(
                    status=Appointment.Status.COMPLETED
                ).count(),

                "cancelled": appointments.filter(
                    status=Appointment.Status.CANCELLED
                ).count(),

                "not_attended": appointments.filter(
                    status=Appointment.Status.NOT_ATTENDED
                ).count(),

                "rescheduled": None,

                "start_date": start_date,
                "end_date": end_date
            }
        )


# --------------------------------------------------
# 4. UPCOMING APPOINTMENTS REPORT
# --------------------------------------------------

class UpcomingAppointmentReportAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        start_date, end_date, error = get_date_range(request)

        if error:
            return CustomResponse.error(message=error)

        appointments = (
            Appointment.objects
            .filter(
                status=Appointment.Status.SCHEDULED,
                appointment_datetime__gte=timezone.now()
            )
            .select_related("patient")
            .order_by("appointment_datetime")
        )

        if end_date:
            appointments = appointments.filter(
                appointment_datetime__date__lte=end_date
            )

        if start_date:
            appointments = appointments.filter(
                appointment_datetime__date__gte=start_date
            )

        result, error = paginate_data(
            request,
            appointments,
            appointment_data
        )

        if error:
            return CustomResponse.error(message=error)

        return CustomResponse.success(
            message="Upcoming appointments retrieved successfully.",
            data=result
        )


# --------------------------------------------------
# 5. PATIENT-WISE VISIT HISTORY
# --------------------------------------------------

class PatientVisitHistoryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):

        patient = Patient.objects.filter(id=patient_id).first()

        if not patient:
            return CustomResponse.error(
                message="Patient not found."
            )

        visits = (
            PatientVisit.objects
            .filter(patient=patient)
            .select_related("patient", "appointment")
            .order_by("-visit_date")
        )

        result, error = paginate_data(
            request,
            visits,
            patient_visit_data
        )

        if error:
            return CustomResponse.error(message=error)

        return CustomResponse.success(
            message="Patient visit history retrieved successfully.",
            data={
                "patient": {
                    "id": str(patient.id),
                    "full_name": patient.full_name,
                    "mobile": patient.mobile
                },
                "visit_history": result
            }
        )


# --------------------------------------------------
# 6. INVOICE AND COLLECTION REPORT
# --------------------------------------------------


class InvoiceReportAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        # Validate date range
        start_date, end_date, error = get_date_range(request)

        if error:
            return CustomResponse.error(message=error)

        # Validate grouping
        group_by = get_grouping(request)

        if not group_by:
            return CustomResponse.error(
                message="Invalid group_by. Use daily or monthly."
            )

        # Filter invoices by invoice date
        invoices = Invoice.objects.all()

        invoices = apply_date_filter(
            invoices,
            "invoice_date",
            start_date,
            end_date
        )

        # Filter payments by payment date
        payments = InvoicePayment.objects.all()

        payments = apply_date_filter(
            payments,
            "payment_date",
            start_date,
            end_date
        )

        # Group invoices by day or month
        invoice_period = get_period_expression(
            group_by,
            "invoice_date"
        )

        invoice_summary = (
            invoices
            .annotate(report_period=invoice_period)
            .values("report_period")
            .annotate(
                invoice_count=Count("id"),
                billed_amount=Sum("total_amount")
            )
            .order_by("report_period")
        )

        # Group payments by day or month
        payment_period = get_period_expression(
            group_by,
            "payment_date"
        )

        payment_summary = (
            payments
            .annotate(report_period=payment_period)
            .values("report_period")
            .annotate(
                payment_count=Count("id"),
                collected_amount=Sum("amount")
            )
            .order_by("report_period")
        )

        # Format invoice summary
        invoice_data = [
            {
                "period": format_period(
                    row["report_period"],
                    group_by
                ),
                "invoice_count": row["invoice_count"],
                "billed_amount": row["billed_amount"] or ZERO
            }
            for row in invoice_summary
        ]

        # Format collection summary
        collection_data = [
            {
                "period": format_period(
                    row["report_period"],
                    group_by
                ),
                "payment_count": row["payment_count"],
                "collected_amount": row["collected_amount"] or ZERO
            }
            for row in payment_summary
        ]

        # Total billed amount for selected invoices
        billed_amount = invoices.aggregate(
            total=Sum("total_amount")
        )["total"] or ZERO

        # Collections received during selected payment date range
        collected_amount = payments.aggregate(
            total=Sum("amount")
        )["total"] or ZERO

        # All payments received against the selected invoices,
        # regardless of when those payments were recorded
        paid_against_invoices = InvoicePayment.objects.filter(
            invoice__in=invoices
        ).aggregate(
            total=Sum("amount")
        )["total"] or ZERO

        # Outstanding balance for selected invoices
        outstanding_balance = billed_amount - paid_against_invoices

        return CustomResponse.success(
            message="Invoice report retrieved successfully.",
            data={
                "group_by": group_by,
                "start_date": start_date,
                "end_date": end_date,
                "total_invoices": invoices.count(),
                "total_billed_amount": billed_amount,
                "total_recorded_collections": collected_amount,
                "balance": outstanding_balance,
                "invoice_summary": invoice_data,
                "collection_summary": collection_data
            }
        )

# --------------------------------------------------
# 7. PRODUCT AND SERVICE BILLING REPORT
# --------------------------------------------------

class BillingSummaryReportAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        start_date, end_date, error = get_date_range(request)

        if error:
            return CustomResponse.error(message=error)

        items = InvoiceItem.objects.filter(
            item_type__in=[
                InvoiceItem.ItemType.CONSULTATION,
                InvoiceItem.ItemType.TREATMENT,
                InvoiceItem.ItemType.PRODUCT
            ]
        )

        items = apply_date_filter(
            items,
            "invoice__invoice_date",
            start_date,
            end_date
        )

        summary = (
            items
            .values("item_type")
            .annotate(
                total_items=Count("id"),
                total_quantity=Sum("quantity"),
                billed_amount=Sum("total_price"),
                gst_amount=Sum("gst_amount")
            )
            .order_by("item_type")
        )

        item_details = (
            items
            .values("item_type", "item_name")
            .annotate(
                total_quantity=Sum("quantity"),
                billed_amount=Sum("total_price"),
                gst_amount=Sum("gst_amount"),
                times_billed=Count("id")
            )
            .order_by("item_type", "item_name")
        )

        return CustomResponse.success(
            message="Product and service billing report retrieved successfully.",
            data={
                "start_date": start_date,
                "end_date": end_date,
                "summary": list(summary),
                "item_details": list(item_details)
            }
        )


# --------------------------------------------------
# 8. COMBINED DASHBOARD REPORT
# --------------------------------------------------

class DashboardReportAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        start_date, end_date, error = get_date_range(request)

        if error:
            return CustomResponse.error(message=error)

        now = timezone.now()

        patients = apply_date_filter(
            Patient.objects.all(),
            "created_at",
            start_date,
            end_date
        )

        visits = apply_date_filter(
            PatientVisit.objects.all(),
            "visit_date",
            start_date,
            end_date
        )

        appointments = apply_date_filter(
            Appointment.objects.all(),
            "appointment_datetime",
            start_date,
            end_date
        )

        invoices = apply_date_filter(
            Invoice.objects.all(),
            "invoice_date",
            start_date,
            end_date
        )

        payments = apply_date_filter(
            InvoicePayment.objects.all(),
            "payment_date",
            start_date,
            end_date
        )

        billed_amount = invoices.aggregate(
            total=Sum("total_amount")
        )["total"] or ZERO

        collected_amount = payments.aggregate(
            total=Sum("amount")
        )["total"] or ZERO

        return CustomResponse.success(
            message="Dashboard report retrieved successfully.",
            data={
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                },

                "patients": {
                    "total_registrations": patients.count(),
                    "active": patients.filter(is_active=True).count(),
                    "inactive": patients.filter(is_active=False).count()
                },

                "visits": {
                    "total_visits": visits.count()
                },

                "appointments": {
                    "total": appointments.count(),

                    "upcoming": appointments.filter(
                        status=Appointment.Status.SCHEDULED,
                        appointment_datetime__gte=now
                    ).count(),

                    "completed": appointments.filter(
                        status=Appointment.Status.COMPLETED
                    ).count(),

                    "cancelled": appointments.filter(
                        status=Appointment.Status.CANCELLED
                    ).count(),

                    "not_attended": appointments.filter(
                        status=Appointment.Status.NOT_ATTENDED
                    ).count()
                },

                "invoices": {
                    "total_invoices": invoices.count(),
                    "billed_amount": billed_amount,
                    "recorded_collections": collected_amount,
                    "balance": billed_amount - collected_amount
                }
            }
        )
