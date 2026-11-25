
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from shared.utils.custom_response import CustomResponse

from db.models import Service


# =========================================================
# CONSTANTS
# =========================================================

FIXED_SERVICE_TYPE = Service.ServiceType.TREATMENT


# =========================================================
# API 1: SERVICE LIST AND CREATION
# =========================================================

class ServiceListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # POST: CREATE SERVICE
    # -----------------------------------------------------

    def post(self, request, format=None):

        required_fields = ["service_name", "price"]

        for field in required_fields:

            if field not in request.data:
                return CustomResponse.error(
                    message=f"{field} is required"
                )

        service_name = request.data.get("service_name")
        description = request.data.get("description")
        is_active = request.data.get("is_active", True)

        # SERVICE TYPE IS FIXED AS TREATMENT
        supplied_type = request.data.get("service_type")

        if (
            supplied_type is not None
            and supplied_type != FIXED_SERVICE_TYPE
        ):
            return CustomResponse.error(
                message="Service type is fixed as TREATMENT."
            )

        # VALIDATE SERVICE NAME
        if not isinstance(service_name, str) or not service_name.strip():

            return CustomResponse.error(
                message="Service name cannot be empty"
            )

        # VALIDATE DESCRIPTION
        if description is not None and not isinstance(description, str):

            return CustomResponse.error(
                message="Description must be a string or null"
            )

        # VALIDATE ACTIVE STATUS
        if not isinstance(is_active, bool):

            return CustomResponse.error(
                message="is_active must be true or false"
            )

        # VALIDATE PRICE
        try:
            price = Decimal(str(request.data.get("price")))

        except (ValueError, TypeError, InvalidOperation):

            return CustomResponse.error(
                message="Invalid price"
            )

        if not price.is_finite() or price < 0:

            return CustomResponse.error(
                message="Price cannot be negative or invalid"
            )

        # CREATE SERVICE
        service = Service(
            service_name=service_name.strip(),
            service_type=FIXED_SERVICE_TYPE,
            description=description,
            price=price,
            is_active=is_active,
            created_by=request.user.username,
            updated_by=request.user.username
        )

        try:
            service.full_clean()

        except ValidationError:

            return CustomResponse.error(
                message="Service validation failed."
            )

        service.save()

        return CustomResponse.success(
            message="Service created successfully.",
            data=self.service_data(service)
        )

    # -----------------------------------------------------
    # COMMON SERVICE RESPONSE
    # -----------------------------------------------------

    @staticmethod
    def service_data(service):

        return {
            "id": str(service.id),
            "service_name": service.service_name,
            "service_type": FIXED_SERVICE_TYPE,
            "description": service.description,
            "price": str(service.price),
            "is_active": service.is_active,
            "created_at": service.created_at,
            "updated_at": service.updated_at
        }

    # -----------------------------------------------------
    # GET: RETRIEVE SERVICES WITH SEARCH, FILTERS
    # AND PAGINATION
    # -----------------------------------------------------

    def get(self, request, format=None):

        services = Service.objects.all().order_by("service_name")

        # SEARCH
        search = request.query_params.get("search")

        if search:
            services = services.filter(
                service_name__icontains=search.strip()
            )

        # SERVICE TYPE FILTER
        # Only TREATMENT is supported.
        service_type = request.query_params.get("service_type")

        if service_type is not None:

            if service_type != FIXED_SERVICE_TYPE:

                return CustomResponse.error(
                    message="Only TREATMENT service type is supported."
                )

            services = services.filter(
                service_type=FIXED_SERVICE_TYPE
            )

        # ACTIVE STATUS FILTER
        is_active = request.query_params.get("is_active")

        if is_active is not None:

            if is_active.lower() not in ["true", "false"]:

                return CustomResponse.error(
                    message="is_active must be true or false"
                )

            services = services.filter(
                is_active=is_active.lower() == "true"
            )

        # PRICE FILTER
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")

        try:

            if min_price is not None:
                min_price = Decimal(min_price)

            if max_price is not None:
                max_price = Decimal(max_price)

            if (
                (min_price is not None and (
                    not min_price.is_finite() or min_price < 0
                ))
                or
                (max_price is not None and (
                    not max_price.is_finite() or max_price < 0
                ))
            ):

                return CustomResponse.error(
                    message="Price filters cannot be negative or invalid"
                )

            if (
                min_price is not None
                and max_price is not None
                and min_price > max_price
            ):

                return CustomResponse.error(
                    message="min_price cannot exceed max_price"
                )

            if min_price is not None:
                services = services.filter(
                    price__gte=min_price
                )

            if max_price is not None:
                services = services.filter(
                    price__lte=max_price
                )

        except (InvalidOperation, ValueError, TypeError):

            return CustomResponse.error(
                message="Invalid price filter"
            )

        # PAGINATION
        try:

            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("size", 20))

            if page < 1 or size < 1 or size > 100:
                raise ValueError

        except (ValueError, TypeError):

            return CustomResponse.error(
                message=(
                    "Invalid page or size. "
                    "Size must be between 1 and 100"
                )
            )

        paginator = Paginator(services, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:

            return CustomResponse.error(
                message="Requested page does not exist"
            )

        results = [
            self.service_data(service)
            for service in page_obj.object_list
        ]

        return CustomResponse.success(
            message="Services retrieved successfully.",
            data={
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page,
                "page_size": size,
                "results": results
            }
        )


# =========================================================
# API 2: SERVICE RETRIEVAL, UPDATE AND DEACTIVATION
# =========================================================

class ServiceDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # GET: RETRIEVE SERVICE BY ID
    # -----------------------------------------------------

    def get(self, request, service_id, format=None):

        service = Service.objects.filter(
            id=service_id
        ).first()

        if not service:

            return CustomResponse.error(
                message="Service not found"
            )

        return CustomResponse.success(
            message="Service retrieved successfully.",
            data=ServiceListCreateAPIView.service_data(service)
        )

    # -----------------------------------------------------
    # PATCH: UPDATE SELECTED FIELDS
    # -----------------------------------------------------

    def patch(self, request, service_id, format=None):

        service = Service.objects.filter(
            id=service_id
        ).first()

        if not service:

            return CustomResponse.error(
                message="Service not found"
            )

        # SERVICE TYPE CANNOT BE CHANGED.
        allowed_fields = {
            "service_name",
            "description",
            "price",
            "is_active"
        }

        if not request.data:

            return CustomResponse.error(
                message="No update data provided"
            )

        unknown_fields = set(request.data.keys()) - allowed_fields

        if unknown_fields:

            if "service_type" in unknown_fields:

                return CustomResponse.error(
                    message="Service type is fixed as TREATMENT and cannot be changed."
                )

            return CustomResponse.error(
                message="Invalid fields provided"
            )

        for field, value in request.data.items():

            # VALIDATE SERVICE NAME
            if field == "service_name":

                if not isinstance(value, str) or not value.strip():

                    return CustomResponse.error(
                        message="Service name cannot be empty"
                    )

                value = value.strip()

            # VALIDATE PRICE
            elif field == "price":

                try:
                    value = Decimal(str(value))

                    if not value.is_finite() or value < 0:
                        raise ValueError

                except (ValueError, TypeError, InvalidOperation):

                    return CustomResponse.error(
                        message="Invalid price"
                    )

            # VALIDATE ACTIVE STATUS
            elif field == "is_active":

                if not isinstance(value, bool):

                    return CustomResponse.error(
                        message="is_active must be true or false"
                    )

            # VALIDATE DESCRIPTION
            elif field == "description":

                if value is not None and not isinstance(value, str):

                    return CustomResponse.error(
                        message="Description must be a string or null"
                    )

            setattr(service, field, value)

        # ENSURE SERVICE TYPE REMAINS TREATMENT
        service.service_type = FIXED_SERVICE_TYPE

        service.updated_by = request.user.username

        try:
            service.full_clean()

        except ValidationError:

            return CustomResponse.error(
                message="Service validation failed."
            )

        service.save()

        return CustomResponse.success(
            message="Service updated successfully.",
            data=ServiceListCreateAPIView.service_data(service)
        )

    # -----------------------------------------------------
    # DELETE: SOFT DELETE SERVICE
    # -----------------------------------------------------

    def delete(self, request, service_id, format=None):

        service = Service.objects.filter(
            id=service_id
        ).first()

        if not service:

            return CustomResponse.error(
                message="Service not found"
            )

        if not service.is_active:

            return CustomResponse.error(
                message="Service is already inactive"
            )

        service.is_active = False
        service.updated_by = request.user.username
        service.save()

        return CustomResponse.success(
            message="Service deactivated successfully."
        )
