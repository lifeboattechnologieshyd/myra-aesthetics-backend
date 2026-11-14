from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

#Import custom responses

from db.models import Product
from shared.utils.custom_response import CustomResponse


class ProductListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # CREATE PRODUCT
    def post(self, request, format=None):

        required_fields = ["product_name", "quantity", "mrp", "price"]

        for field in required_fields:
            if field not in request.data:
                return CustomResponse.error(
                    message=f"{field} is required"
                )

        product_name = request.data.get("product_name")

        if not isinstance(product_name, str) or not product_name.strip():
            return CustomResponse.error(
                message="Product name cannot be empty"
            )

        description = request.data.get("description")
        is_active = request.data.get("is_active", True)

        if description is not None and not isinstance(description, str):
            return CustomResponse.error(
                message="Description must be a string or null"
            )

        if not isinstance(is_active, bool):
            return CustomResponse.error(
                message= "is_active must be true or false"
            )

        try:
            quantity = int(request.data.get("quantity"))
            mrp = Decimal(str(request.data.get("mrp")))
            price = Decimal(str(request.data.get("price")))

        except (ValueError, TypeError, InvalidOperation):
            return CustomResponse.error(
                message= "Invalid quantity or price"
            )

        if quantity < 0 or mrp < 0 or price < 0:
            return CustomResponse.error(
                message= "Quantity and prices cannot be negative"
            )

        if mrp < price:
            return CustomResponse.error(
                message= "Selling price cannot exceed MRP"
            )

        product = Product(
            product_name=product_name.strip(),
            description=description,
            quantity=quantity,
            mrp=mrp,
            price=price,
            is_active=is_active,
            created_by=request.user.username,
            updated_by=request.user.username
        )

        try:
            product.full_clean()
        except ValidationError as error:
            return CustomResponse.error(
                message="Product validation failed.",
            )

        product.save()

        return CustomResponse.success(
            message="Product created successfully.",
            data=self.product_data(product)
        )

    # COMMON PRODUCT RESPONSE
    @staticmethod
    def product_data(product):

        return {
            "id": str(product.id),
            "product_name": product.product_name,
            "description": product.description,
            "quantity": product.quantity,
            "mrp": str(product.mrp),
            "price": str(product.price),
            "is_active": product.is_active,
            "created_at": product.created_at,
            "updated_at": product.updated_at
        }

    # RETRIEVE PRODUCTS WITH PAGINATION, SEARCH AND FILTERS
    def get(self, request, format=None):

        products = Product.objects.all().order_by("-created_at")

        # SEARCH
        search = request.query_params.get("search")

        if search:
            products = products.filter(
                product_name__icontains=search.strip()
            )

        # ACTIVE STATUS FILTER
        is_active = request.query_params.get("is_active")

        if is_active is not None:

            if is_active.lower() not in ["true", "false"]:
                return CustomResponse.error(
                    message="is_active must be true or false"
                )

            products = products.filter(
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
                min_price is not None
                and max_price is not None
                and min_price > max_price
            ):
                return CustomResponse.error(
                    message="min_price cannot exceed max_price"
                )

            if min_price is not None:
                products = products.filter(price__gte=min_price)

            if max_price is not None:
                products = products.filter(price__lte=max_price)

        except InvalidOperation:
            return CustomResponse.error(
                message="Invalid price filter"
            )

        # QUANTITY FILTER
        min_quantity = request.query_params.get("min_quantity")

        if min_quantity is not None:

            try:
                min_quantity = int(min_quantity)

                if min_quantity < 0:
                    raise ValueError

                products = products.filter(
                    quantity__gte=min_quantity
                )

            except ValueError:
                return CustomResponse.error(
                    message= "Invalid min_quantity"
                )

        # PAGINATION
        try:
            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("size", 20))

            if page < 1 or size < 1 or size > 100:
                raise ValueError

        except (ValueError, TypeError):
            return CustomResponse.error(
                message= "Invalid page or size. Size must be between 1 and 100"
            )

        paginator = Paginator(products, size)

        try:
            page_obj = paginator.page(page)

        except EmptyPage:
            return CustomResponse.error(
                message= "Requested page does not exist"
            )

        results = [
            self.product_data(product)
            for product in page_obj.object_list
        ]

        return CustomResponse.success(
            message="Products retrieved successfully.",
            data={
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page,
                "page_size": size,
                "results": results
            }
        )


class ProductDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    # GET PRODUCT BY ID
    def get(self, request, product_id, format=None):

        try:
            product = Product.objects.get(id=product_id)

        except Product.DoesNotExist:
            return CustomResponse.error(
                message= "Product not found"
            )

        return CustomResponse.success(
            message="Product retrieved successfully.",
            data=ProductListCreateAPIView.product_data(product)
        )

    # COMMON UPDATE METHOD
    def update_product(self, request, product, partial):

        allowed_fields = {
            "product_name",
            "description",
            "quantity",
            "mrp",
            "price",
            "is_active"
        }

        if not request.data:
            return CustomResponse.error(
                message="No update data provided"
            )

        if set(request.data.keys()) - allowed_fields:
            return CustomResponse.error(
                message="Invalid fields provided"
            )

        if not partial:
            required_fields = {
                "product_name",
                "quantity",
                "mrp",
                "price",
                "is_active"
            }

            missing_fields = required_fields - set(request.data.keys())

            if missing_fields:
                return CustomResponse.error(
                    message=f"Missing fields: {list(missing_fields)}"
                )

        for field, value in request.data.items():

            if field == "product_name":
                if not isinstance(value, str) or not value.strip():
                    return CustomResponse.error(
                        message="Product name cannot be empty"
                    )

                value = value.strip()

            elif field == "quantity":
                try:
                    value = int(value)
                    if value < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    return CustomResponse.error(
                        message= "Invalid quantity"
                    )

            elif field in ["mrp", "price"]:
                try:
                    value = Decimal(str(value))
                    if value < 0:
                        raise ValueError
                except (ValueError, TypeError, InvalidOperation):
                    return CustomResponse.error(
                        message=f"Invalid {field}"
                    )

            elif field == "is_active":
                if not isinstance(value, bool):
                    return CustomResponse.error(
                        message="is_active must be true or false"
                    )

            elif field == "description":
                if value is not None and not isinstance(value, str):
                    return CustomResponse.error(
                        message="Description must be a string or null"
                    )

            setattr(product, field, value)

        if product.mrp < product.price:
            return CustomResponse.error(
                message="Selling price cannot exceed MRP"
            )

        product.updated_by = request.user.username

        try:
            product.full_clean()
        except ValidationError as error:
            return CustomResponse.error(
                message="Product validation failed.",
            )

        product.save()

        return CustomResponse.success(
            message="Product updated successfully.",
            data=ProductListCreateAPIView.product_data(product)
        )

    # UPDATE ALL FIELDS
    def put(self, request, product_id, format=None):

        try:
            product = Product.objects.get(id=product_id)

        except Product.DoesNotExist:
            return CustomResponse.error(
                message="Product not found"
            )

        return self.update_product(request, product, partial=False)

    # UPDATE SELECTED FIELDS
    def patch(self, request, product_id, format=None):

        try:
            product = Product.objects.get(id=product_id)

        except Product.DoesNotExist:
            return CustomResponse.error(
                message="Product not found"
            )

        return self.update_product(request, product, partial=True)

    # SOFT DELETE PRODUCT
    def delete(self, request, product_id, format=None):

        # Find the product
        product = Product.objects.filter(id=product_id).first()

        if not product:
            return CustomResponse.error(
                message="Product not found"
            )

        # Check whether the product is already inactive
        if not product.is_active:
            return CustomResponse.error(
                message= "Product is already inactive"
            )

        # Mark product as inactive instead of permanently deleting it
        product.is_active = False
        product.updated_by = request.user.username
        product.save()

        return CustomResponse.success(
            message="Product deactivated successfully."
        )
