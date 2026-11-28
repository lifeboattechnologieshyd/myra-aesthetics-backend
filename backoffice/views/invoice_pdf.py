
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from db.models import Invoice
from shared.utils.custom_response import CustomResponse
from shared.utils.invoice_service import generate_invoice_pdf


class InvoicePDFAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):

        # Check whether the invoice exists.
        try:
            invoice = Invoice.objects.get(id=invoice_id)

        except Invoice.DoesNotExist:
            return CustomResponse.error(
                message="Invoice not found."
            )

        # Return the existing PDF URL if already generated.
        if invoice.invoice_pdf:
            return CustomResponse.success(
                message="Invoice PDF already generated.",
                data={
                    "invoice_id": str(invoice.id),
                    "invoice_pdf": invoice.invoice_pdf
                }
            )

        # Generate the PDF if it does not exist.
        result = generate_invoice_pdf(invoice_id)

        # Check whether PDF generation was successful.
        if not result.get("success"):
            return CustomResponse.error(
                message=result.get(
                    "message",
                    "Unable to generate invoice PDF."
                )
            )

        return CustomResponse.success(
            message="Invoice PDF generated successfully.",
            data=result
        )
