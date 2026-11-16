from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from shared.utils.custom_response import CustomResponse

from db.models import Patient, Service, Product, Invoice, InvoiceItem


TWO_PLACES = Decimal("0.01")


# COMMON DECIMAL VALIDATION
def to_decimal(value):

    try:
        amount = Decimal(str(value))

        if not amount.is_finite():
            raise ValueError

        return amount

    except (ValueError, TypeError, InvalidOperation):
        raise ValueError("Invalid decimal value")


# ROUND AMOUNTS TO TWO DECIMAL PLACES
def money(value):

    return value.quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP
    )


# GET GST RATE FROM SETTINGS
def get_gst_rate(item_type, billing_type):

    if billing_type == Invoice.BillingType.NON_GST:
        return Decimal("0.00")

    if item_type in [
        InvoiceItem.ItemType.CONSULTATION,
        InvoiceItem.ItemType.TREATMENT
    ]:
        rate = settings.SERVICE_GST_RATE

    elif item_type == InvoiceItem.ItemType.PRODUCT:
        rate = settings.PRODUCT_GST_RATE

    elif item_type == InvoiceItem.ItemType.CUSTOM:
        rate = settings.CUSTOM_CHARGE_GST_RATE

    else:
        raise ValueError("Invalid item type")

    rate = to_decimal(rate)

    if rate < 0 or rate > 100:
        raise ValueError("Invalid GST configuration in settings")

    return rate


# GENERATE UNIQUE INVOICE NUMBER
def generate_invoice_number():

    while True:

        invoice_number = (
            f"MYR-{timezone.localdate().strftime('%Y%m%d')}-"
            f"{uuid4().hex[:8].upper()}"
        )

        if not Invoice.objects.filter(
            invoice_number=invoice_number
        ).exists():

            return invoice_number


# COMMON INVOICE ITEM RESPONSE
def invoice_item_data(item):

    return {
        "id": str(item.id),
        "item_type": item.item_type,
        "item_name": item.item_name,
        "service_id": str(item.service_id) if item.service_id else None,
        "product_id": str(item.product_id) if item.product_id else None,
        "quantity": str(item.quantity),
        "unit_price": str(item.unit_price),
        "total_price": str(item.total_price),
        "gst_rate": str(item.gst_rate),
        "gst_amount": str(item.gst_amount)
    }


# COMMON PAYMENT RESPONSE
def invoice_payment_data(payment):

    return {
        "id": str(payment.id),
        "amount": str(payment.amount),
        "payment_method": payment.payment_method,
        "payment_date": payment.payment_date,
        "reference_number": payment.reference_number
    }


# CALCULATE INVOICE TOTALS
def update_invoice_totals(invoice):

    items = list(invoice.items.all())

    subtotal = money(
        sum(
            (item.total_price for item in items),
            Decimal("0.00")
        )
    )

    discount = money(invoice.discount_amount)

    if discount < 0 or discount > subtotal:
        raise ValueError("Discount cannot exceed subtotal")

    taxable_amount = money(subtotal - discount)

    gst_amount = Decimal("0.00")
    remaining_discount = discount

    for index, item in enumerate(items):

        # Allocate discount proportionally across invoice items.
        if index == len(items) - 1:
            item_discount = remaining_discount

        elif subtotal > 0:
            item_discount = money(
                discount * item.total_price / subtotal
            )
            remaining_discount -= item_discount

        else:
            item_discount = Decimal("0.00")

        item_taxable_amount = money(
            item.total_price - item_discount
        )

        item.gst_amount = money(
            item_taxable_amount * item.gst_rate / Decimal("100")
        )

        item.updated_by = invoice.updated_by

        item.save(
            update_fields=[
                "gst_amount",
                "updated_by",
                "updated_at"
            ]
        )

        gst_amount += item.gst_amount

    gst_amount = money(gst_amount)

    invoice.subtotal = subtotal
    invoice.taxable_amount = taxable_amount
    invoice.gst_amount = gst_amount
    invoice.total_amount = money(taxable_amount + gst_amount)

    # Invoice-level rate is a summary only.
    # Individual rates are preserved on InvoiceItem.
    gst_rates = {item.gst_rate for item in items}

    invoice.gst_rate = (
        next(iter(gst_rates))
        if len(gst_rates) == 1
        else Decimal("0.00")
    )

    invoice.save()


# UPDATE PAYMENT STATUS
def update_payment_status(invoice):

    paid_amount = sum(
        (
            payment.amount
            for payment in invoice.payments.all()
        ),
        Decimal("0.00")
    )

    if paid_amount <= 0:
        invoice.payment_status = Invoice.PaymentStatus.PENDING

    elif paid_amount >= invoice.total_amount:
        invoice.payment_status = Invoice.PaymentStatus.PAID

    else:
        invoice.payment_status = (
            Invoice.PaymentStatus.PARTIALLY_PAID
        )

    invoice.save(
        update_fields=[
            "payment_status",
            "updated_at"
        ]
    )


# COMMON INVOICE RESPONSE
def invoice_data(invoice, include_details=False):

    data = {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "patient_id": str(invoice.patient_id),
        "patient_name": invoice.patient.full_name,
        "invoice_date": invoice.invoice_date,
        "billing_type": invoice.billing_type,
        "subtotal": str(invoice.subtotal),
        "discount_amount": str(invoice.discount_amount),
        "taxable_amount": str(invoice.taxable_amount),
        "gst_rate": str(invoice.gst_rate),
        "gst_amount": str(invoice.gst_amount),
        "total_amount": str(invoice.total_amount),
        "payment_status": invoice.payment_status
    }

    if include_details:

        payments = list(invoice.payments.all())

        paid_amount = sum(
            (payment.amount for payment in payments),
            Decimal("0.00")
        )

        data["items"] = [
            invoice_item_data(item)
            for item in invoice.items.all()
        ]

        data["payments"] = [
            invoice_payment_data(payment)
            for payment in payments
        ]

        data["paid_amount"] = str(money(paid_amount))

        data["balance_amount"] = str(
            money(invoice.total_amount - paid_amount)
        )

    return data


class InvoiceListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # CREATE INVOICE WITH ITEMS
    @transaction.atomic
    def post(self, request, format=None):

        required_fields = [
            "patient_id",
            "billing_type",
            "items"
        ]

        for field in required_fields:

            if field not in request.data:
                return CustomResponse.error(
                    message=f"{field} is required"
                )

        patient = Patient.objects.filter(
            id=request.data.get("patient_id"),
            is_active=True
        ).first()

        if not patient:
            return CustomResponse.error(
                message="Active patient not found"
            )

        billing_type = request.data.get("billing_type")

        if billing_type not in Invoice.BillingType.values:
            return CustomResponse.error(
                message="Invalid billing_type"
            )

        items_data = request.data.get("items")

        if (
            not isinstance(items_data, list)
            or not items_data
            or len(items_data) > 100
        ):
            return CustomResponse.error(
                message="Provide between 1 and 100 invoice items"
            )

        try:
            discount = money(
                to_decimal(
                    request.data.get("discount_amount", 0)
                )
            )

            if discount < 0:
                raise ValueError("Discount cannot be negative")

        except ValueError as error:
            return CustomResponse.error(message=str(error))

        invoice_date = timezone.now()

        if "invoice_date" in request.data:

            supplied_date = request.data.get("invoice_date")

            if not isinstance(supplied_date, str):
                return CustomResponse.error(
                    message="Invalid invoice_date"
                )

            invoice_date = parse_datetime(supplied_date)

            if invoice_date is None:
                return CustomResponse.error(
                    message="Invalid invoice_date. Use ISO datetime format"
                )

            if timezone.is_naive(invoice_date):
                invoice_date = timezone.make_aware(invoice_date)

        invoice = Invoice(
            invoice_number=generate_invoice_number(),
            patient=patient,
            invoice_date=invoice_date,
            billing_type=billing_type,
            discount_amount=discount,
            created_by=request.user.username,
            updated_by=request.user.username
        )

        try:

            invoice.full_clean()
            invoice.save()

            for item_data in items_data:

                if not isinstance(item_data, dict):
                    raise ValueError(
                        "Each invoice item must be an object"
                    )

                item_type = item_data.get("item_type")

                if item_type not in InvoiceItem.ItemType.values:
                    raise ValueError("Invalid item_type")

                quantity = to_decimal(
                    item_data.get("quantity", 1)
                )

                if quantity <= 0:
                    raise ValueError(
                        "Quantity must be greater than zero"
                    )

                service = None
                product = None

                # CONSULTATION / TREATMENT
                if item_type in [
                    InvoiceItem.ItemType.CONSULTATION,
                    InvoiceItem.ItemType.TREATMENT
                ]:

                    if item_data.get("product_id"):
                        raise ValueError(
                            "Service item cannot contain product_id"
                        )

                    service = Service.objects.filter(
                        id=item_data.get("service_id"),
                        is_active=True
                    ).first()

                    if not service:
                        raise ValueError("Active service not found")

                    if service.service_type != item_type:
                        raise ValueError(
                            "Service type does not match item_type"
                        )

                    item_name = service.service_name
                    unit_price = service.price

                # PRODUCT
                elif item_type == InvoiceItem.ItemType.PRODUCT:

                    if item_data.get("service_id"):
                        raise ValueError(
                            "Product item cannot contain service_id"
                        )

                    product = Product.objects.filter(
                        id=item_data.get("product_id"),
                        is_active=True
                    ).first()

                    if not product:
                        raise ValueError("Active product not found")

                    item_name = product.product_name
                    unit_price = product.price

                # CUSTOM CHARGE
                else:

                    if (
                        item_data.get("service_id")
                        or item_data.get("product_id")
                    ):
                        raise ValueError(
                            "Custom item cannot reference service or product"
                        )

                    item_name = item_data.get("item_name")

                    if (
                        not isinstance(item_name, str)
                        or not item_name.strip()
                    ):
                        raise ValueError(
                            "Custom item_name is required"
                        )

                    unit_price = to_decimal(
                        item_data.get("unit_price")
                    )

                if unit_price < 0:
                    raise ValueError(
                        "Unit price cannot be negative"
                    )

                gst_rate = get_gst_rate(
                    item_type,
                    billing_type
                )

                unit_price = money(unit_price)

                total_price = money(
                    unit_price * quantity
                )

                invoice_item = InvoiceItem(
                    invoice=invoice,
                    service=service,
                    product=product,
                    item_type=item_type,
                    item_name=item_name.strip(),
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    gst_rate=gst_rate,
                    gst_amount=Decimal("0.00"),
                    created_by=request.user.username,
                    updated_by=request.user.username
                )

                invoice_item.full_clean()
                invoice_item.save()

            update_invoice_totals(invoice)

            return CustomResponse.success(
                message="Invoice created successfully.",
                data=invoice_data(
                    invoice,
                    include_details=True
                )
            )

        except (ValidationError, ValueError, TypeError, InvalidOperation) as error:

            transaction.set_rollback(True)

            return CustomResponse.error(
                message=str(error) or "Invoice validation failed"
            )

    # GET INVOICES WITH FILTERS AND PAGINATION
    def get(self, request, format=None):

        invoices = Invoice.objects.select_related(
            "patient"
        ).all().order_by("-invoice_date")

        invoice_number = request.query_params.get("invoice_number")
        patient_id = request.query_params.get("patient_id")
        payment_status = request.query_params.get("payment_status")
        billing_type = request.query_params.get("billing_type")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if invoice_number:
            invoices = invoices.filter(
                invoice_number__icontains=invoice_number.strip()
            )

        if patient_id:
            invoices = invoices.filter(
                patient_id=patient_id
            )

        if payment_status:

            if payment_status not in Invoice.PaymentStatus.values:
                return CustomResponse.error(
                    message="Invalid payment_status"
                )

            invoices = invoices.filter(
                payment_status=payment_status
            )

        if billing_type:

            if billing_type not in Invoice.BillingType.values:
                return CustomResponse.error(
                    message="Invalid billing_type"
                )

            invoices = invoices.filter(
                billing_type=billing_type
            )

        parsed_start = None
        parsed_end = None

        if start_date:

            parsed_start = parse_date(start_date)

            if parsed_start is None:
                return CustomResponse.error(
                    message="Invalid start_date. Use YYYY-MM-DD"
                )

            invoices = invoices.filter(
                invoice_date__date__gte=parsed_start
            )

        if end_date:

            parsed_end = parse_date(end_date)

            if parsed_end is None:
                return CustomResponse.error(
                    message="Invalid end_date. Use YYYY-MM-DD"
                )

            invoices = invoices.filter(
                invoice_date__date__lte=parsed_end
            )

        if (
            parsed_start
            and parsed_end
            and parsed_start > parsed_end
        ):
            return CustomResponse.error(
                message="start_date cannot be after end_date"
            )

        try:

            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("size", 20))

            if page < 1 or size < 1 or size > 100:
                raise ValueError

        except (ValueError, TypeError):
            return CustomResponse.error(
                message="Invalid page or size. Size must be between 1 and 100"
            )

        paginator = Paginator(invoices, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:
            return CustomResponse.error(
                message="Requested page does not exist"
            )

        results = [
            invoice_data(invoice)
            for invoice in page_obj.object_list
        ]

        return CustomResponse.success(
            message="Invoices retrieved successfully.",
            data={
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page,
                "page_size": size,
                "results": results
            }
        )


class InvoiceDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # GET INVOICE BY ID
    def get(self, request, invoice_id, format=None):

        invoice = Invoice.objects.select_related(
            "patient"
        ).filter(id=invoice_id).first()

        if not invoice:
            return CustomResponse.error(
                message="Invoice not found"
            )

        return CustomResponse.success(
            message="Invoice retrieved successfully.",
            data=invoice_data(
                invoice,
                include_details=True
            )
        )

    # UPDATE INVOICE
    @transaction.atomic
    def patch(self, request, invoice_id, format=None):

        invoice = Invoice.objects.select_for_update().filter(
            id=invoice_id
        ).first()

        if not invoice:
            return CustomResponse.error(
                message="Invoice not found"
            )

        allowed_fields = {
            "invoice_date",
            "discount_amount"
        }

        if not request.data:
            return CustomResponse.error(
                message="No update data provided"
            )

        if set(request.data.keys()) - allowed_fields:
            return CustomResponse.error(
                message="Invalid fields provided"
            )

        if (
            "discount_amount" in request.data
            and invoice.payments.exists()
        ):
            return CustomResponse.error(
                message="Discount cannot be changed after a payment is recorded"
            )

        if "invoice_date" in request.data:

            value = request.data.get("invoice_date")

            if not isinstance(value, str):
                return CustomResponse.error(
                    message="Invalid invoice_date"
                )

            value = parse_datetime(value)

            if value is None:
                return CustomResponse.error(
                    message="Invalid invoice_date. Use ISO datetime format"
                )

            if timezone.is_naive(value):
                value = timezone.make_aware(value)

            invoice.invoice_date = value

        if "discount_amount" in request.data:

            try:
                discount = money(
                    to_decimal(
                        request.data.get("discount_amount")
                    )
                )

                if discount < 0 or discount > invoice.subtotal:
                    raise ValueError(
                        "Discount cannot be negative or exceed subtotal"
                    )

                invoice.discount_amount = discount

            except ValueError as error:
                return CustomResponse.error(
                    message=str(error)
                )

        invoice.updated_by = request.user.username
        invoice.save()

        if "discount_amount" in request.data:
            update_invoice_totals(invoice)

        return CustomResponse.success(
            message="Invoice updated successfully.",
            data=invoice_data(
                invoice,
                include_details=True
            )
        )