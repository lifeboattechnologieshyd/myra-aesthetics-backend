
from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from rest_framework_simplejwt.tokens import RefreshToken

from db.models import UserMaster, PasswordResetRequest
from shared.utils.custom_response import CustomResponse


#Import custom responses


# LOGIN
class LoginAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request, format=None):

        # Get username and password from request body
        username = request.data.get("username")
        password = request.data.get("password")

        # Validate required fields
        if not username or not password:
            return CustomResponse.error(
                message="Username and password are required"
            )

        # Authenticate user credentials
        user = authenticate(
            request,
            username=username,
            password=password
        )

        # Check whether credentials are valid
        if user is None:
            return CustomResponse.error(
                message="Invalid username or password"
            )

        # Generate refresh token
        refresh = RefreshToken.for_user(user)

        # Generate access token from refresh token
        access = refresh.access_token

        # Return login details and both tokens
        return CustomResponse.success(
            message="Login successful",
            data={
                "user_id": str(user.id),
                "username": user.username,
                "access": str(access),
                "refresh": str(refresh)
            }
        )


# CREATE USER
class CreateUserAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):

        # Only superuser can create staff users
        if not request.user.is_superuser:
            return CustomResponse.error(
                message="Only superuser can create users"
            )

        username = request.data.get("username")
        password = request.data.get("password")

        # Validate required fields
        if not username or not password:
            return CustomResponse.error(
                message="Username and password are required"
            )
        username = username.strip()
        if not username:
            return CustomResponse.error(
                message="Username cannot be empty"
            )

        # Check whether username already exists
        if UserMaster.objects.filter(username=username).exists():
            return CustomResponse.error(
                message="Username already exists"
            )
        # Create staff user
        user = UserMaster.objects.create_user(
            username=username,
            password=password,
            is_active=True,
            is_staff=True,
            is_superuser=False
        )

        return CustomResponse.success(
            message="User created successfully",
            data={
                "user_id": str(user.id),
                "username": user.username
            }
        )


# FORGOT PASSWORD
class ForgotPasswordAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request, format=None):

        username = request.data.get("username")

        # Validate username
        if not username:
            return CustomResponse.error(
                message="Username is required"
            )

        username = username.strip()

        # Find active user
        user = UserMaster.objects.filter(
            username=username,
            is_active=True
        ).first()

        # Create password reset request
        PasswordResetRequest.objects.create(
            user=user,
            username=username
        )

        return CustomResponse.success(
            message="Please contact the administrator to reset your password."
        )


# RESET USER PASSWORD
class ResetUserPasswordAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):

        # Only superuser can reset staff passwords
        if not request.user.is_superuser:
            return CustomResponse.error(
                message="Only superuser can reset passwords"
            )

        username = request.data.get("username")
        new_password = request.data.get("new_password")

        # Validate required fields
        if not username or not new_password :
            return CustomResponse.error(
                message="Username and new_password are required"
            )

        username = username.strip()


        # Find staff user
        user = UserMaster.objects.filter(
            username=username,
            is_superuser=False
        ).first()

        if not user:
            return CustomResponse.error(
                message="Staff user not found"
            )



        # Update password
        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Blacklist all existing refresh tokens for this user
        outstanding_tokens = OutstandingToken.objects.filter(user=user)

        for token in outstanding_tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return CustomResponse.success(
            message="User password reset success"
        )
