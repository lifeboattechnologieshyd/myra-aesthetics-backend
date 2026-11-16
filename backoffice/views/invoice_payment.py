from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from shared.utils.custom_response import CustomResponse

from db.models import Invoice, InvoicePayment


TWO_PLACES = Decimal("0.01")


# COMMON DECIMAL VALIDATION
def to_decimal(value):

    try:
        amount = Decimal(str(value))

        if not amount.is_finite():
            raise ValueError

        return amount.quantize(
            TWO_PLACES,
            rounding=ROUND_HALF_UP
        )

    except (ValueError, TypeError, InvalidOperation):
        raise ValueError("Invalid payment amount")


# COMMON PAYMENT RESPONSE
def payment_data(payment):

    return {
        "id": str(payment.id),
        "amount": str(payment.amount),
        "payment_method": payment.payment_method,
        "payment_date": payment.payment_date,
        "reference_number": payment.reference_number
    }


# RECORD PAYMENT AND UPDATE INVOICE PAYMENT STATUS
class InvoicePaymentAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # RECORD PAYMENT
    @transaction.atomic
    def post(self, request, invoice_id, format=None):

        invoice = Invoice.objects.select_for_update().filter(
            id=invoice_id
        ).first()

        if not invoice:
            return CustomResponse.error(
                message="Invoice not found"
            )

        required_fields = [
            "amount",
            "payment_method"
        ]

        for field in required_fields:

            if field not in request.data:
                return CustomResponse.error(
                    message=f"{field} is required"
                )

        try:
            amount = to_decimal(
                request.data.get("amount")
            )

            if amount <= 0:
                raise ValueError(
                    "Payment amount must be greater than zero"
                )

        except ValueError as error:
            return CustomResponse.error(
                message=str(error)
            )

        payment_method = request.data.get("payment_method")

        if payment_method not in InvoicePayment.PaymentMethod.values:
            return CustomResponse.error(
                message="Invalid payment_method"
            )

        reference_number = request.data.get("reference_number")

        if (
            reference_number is not None
            and not isinstance(reference_number, str)
        ):
            return CustomResponse.error(
                message="reference_number must be a string or null"
            )

        payment_date = timezone.now()

        if "payment_date" in request.data:

            supplied_date = request.data.get("payment_date")

            if not isinstance(supplied_date, str):
                return CustomResponse.error(
                    message="Invalid payment_date"
                )

            payment_date = parse_datetime(supplied_date)

            if payment_date is None:
                return CustomResponse.error(
                    message="Invalid payment_date. Use ISO datetime format"
                )

            if timezone.is_naive(payment_date):
                payment_date = timezone.make_aware(payment_date)

        paid_amount = sum(
            (
                payment.amount
                for payment in invoice.payments.all()
            ),
            Decimal("0.00")
        )

        balance_amount = invoice.total_amount - paid_amount

        if amount > balance_amount:
            return CustomResponse.error(
                message="Payment cannot exceed outstanding balance"
            )

        payment = InvoicePayment(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            payment_date=payment_date,
            reference_number=reference_number,
            created_by=request.user.username,
            updated_by=request.user.username
        )

        try:
            payment.full_clean()
            payment.save()

        except ValidationError as error:
            transaction.set_rollback(True)

            return CustomResponse.error(
                message=str(error)
            )

        paid_amount += amount

        if paid_amount >= invoice.total_amount:
            invoice.payment_status = Invoice.PaymentStatus.PAID

        elif paid_amount > 0:
            invoice.payment_status = (
                Invoice.PaymentStatus.PARTIALLY_PAID
            )

        else:
            invoice.payment_status = Invoice.PaymentStatus.PENDING

        invoice.updated_by = request.user.username

        invoice.save(
            update_fields=[
                "payment_status",
                "updated_by",
                "updated_at"
            ]
        )

        return CustomResponse.success(
            message="Payment recorded successfully.",
            data={
                "payment": payment_data(payment),
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "total_amount": str(invoice.total_amount),
                "paid_amount": str(paid_amount),
                "balance_amount": str(
                    balance_amount - amount
                ),
                "payment_status": invoice.payment_status
            }
        )

    # GET PAYMENT HISTORY
    def get(self, request, invoice_id, format=None):

        invoice = Invoice.objects.filter(
            id=invoice_id
        ).first()

        if not invoice:
            return CustomResponse.error(
                message="Invoice not found"
            )

        payments = invoice.payments.all()

        results = [
            payment_data(payment)
            for payment in payments
        ]

        paid_amount = sum(
            (
                payment.amount
                for payment in payments
            ),
            Decimal("0.00")
        )

        return CustomResponse.success(
            message="Payment history retrieved successfully.",
            data={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "total_amount": str(invoice.total_amount),
                "paid_amount": str(paid_amount),
                "balance_amount": str(
                    invoice.total_amount - paid_amount
                ),
                "payment_status": invoice.payment_status,
                "payments": results
            }
        )