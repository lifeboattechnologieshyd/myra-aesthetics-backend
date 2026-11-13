
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken
)

from db.models import UserMaster, PasswordResetRequest


# LOGIN
class LoginAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request, format=None):

        # Get username and password from request body
        username = request.data.get("username")
        password = request.data.get("password")

        # Validate required fields
        if not username or not password:
            return Response(
                {"message": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user credentials
        user = authenticate(
            request,
            username=username,
            password=password
        )

        # Check whether credentials are valid
        if user is None:
            return Response(
                {"message": "Invalid username or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate refresh token
        refresh = RefreshToken.for_user(user)

        # Generate access token from refresh token
        access = refresh.access_token

        # Return login details and both tokens
        return Response(
            {
                "message": "Login successful",
                "user_id": str(user.id),
                "username": user.username,
                "access": str(access),
                "refresh": str(refresh)
            },
            status=status.HTTP_200_OK
        )


# CREATE USER
class CreateUserAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):

        # Only superuser can create staff users
        if not request.user.is_superuser:
            return Response(
                {"message": "Only superuser can create users"},
                status=status.HTTP_403_FORBIDDEN
            )

        username = request.data.get("username")
        password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")

        # Validate required fields
        if not username or not password or not confirm_password:
            return Response(
                {
                    "message": "Username, password and confirm_password are required"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        username = username.strip()

        # Check whether username already exists
        if UserMaster.objects.filter(username=username).exists():
            return Response(
                {"message": "Username already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check password confirmation
        if password != confirm_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate password strength
        try:
            validate_password(password)
        except ValidationError as error:
            return Response(
                {"message": error.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create staff user
        user = UserMaster.objects.create_user(
            username=username,
            password=password,
            is_active=True,
            is_staff=False,
            is_superuser=False
        )

        return Response(
            {
                "message": "User created successfully",
                "user_id": str(user.id),
                "username": user.username
            },
            status=status.HTTP_201_CREATED
        )


# FORGOT PASSWORD
class ForgotPasswordAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request, format=None):

        username = request.data.get("username")

        # Validate username
        if not username:
            return Response(
                {"message": "Username is required"},
                status=status.HTTP_400_BAD_REQUEST
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

        return Response(
            {
                "message": "Please contact the administrator to reset your password."
            },
            status=status.HTTP_200_OK
        )


# RESET USER PASSWORD
class ResetUserPasswordAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):

        # Only superuser can reset staff passwords
        if not request.user.is_superuser:
            return Response(
                {"message": "Only superuser can reset passwords"},
                status=status.HTTP_403_FORBIDDEN
            )

        username = request.data.get("username")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        # Validate required fields
        if not username or not new_password or not confirm_password:
            return Response(
                {
                    "message": "Username, new_password and confirm_password are required"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        username = username.strip()

        # Check password confirmation
        if new_password != confirm_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find staff user
        user = UserMaster.objects.filter(
            username=username,
            is_superuser=False
        ).first()

        if not user:
            return Response(
                {"message": "Staff user not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate new password
        try:
            validate_password(new_password, user=user)
        except ValidationError as error:
            return Response(
                {"message": error.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update password
        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Blacklist all existing refresh tokens for this user
        outstanding_tokens = OutstandingToken.objects.filter(user=user)

        for token in outstanding_tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return Response(
            {"message": "User password reset successfully"},
            status=status.HTTP_200_OK
        )
