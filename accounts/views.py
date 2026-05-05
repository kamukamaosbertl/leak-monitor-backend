from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from firebase_admin import auth as firebase_auth

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ProfileSetupSerializer,
)


def get_tokens_for_user(user):
    """Generate JWT refresh and access tokens for a user."""
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def build_auth_response(user):
    """Return the standard auth response used by login/register/google login."""
    return {
        "user": UserSerializer(user).data,
        "tokens": get_tokens_for_user(user),
    }


def get_unique_username_from_email(email):
    """Create a safe unique username from an email address."""
    base_username = email.split("@")[0].lower().replace(" ", "_")
    username = base_username
    counter = 1

    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1

    return username


class RegisterView(APIView):
    """POST /api/auth/register/"""

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response(
                build_auth_response(user),
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    POST /api/auth/login/

    Supports username or email.
    Uses filter().first() instead of get() to avoid crashing
    when duplicate emails already exist in the database.
    """

    def post(self, request):
        username_or_email = request.data.get("username", "").strip()
        password = request.data.get("password", "").strip()

        if not username_or_email or not password:
            return Response(
                {"error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try username first.
        user_obj = User.objects.filter(username=username_or_email).first()

        # If username was not found, try email.
        if user_obj is None:
            user_obj = (
                User.objects
                .filter(email=username_or_email)
                .order_by("id")
                .first()
            )

        if user_obj is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Django authenticate expects username, not email.
        user = authenticate(
            username=user_obj.username,
            password=password,
        )

        if user is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(build_auth_response(user), status=status.HTTP_200_OK)


class ProfileSetupView(APIView):
    """
    PUT /api/auth/profile/setup/

    Completes the user profile after signup/login.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request):
        profile = request.user.profile

        serializer = ProfileSetupSerializer(
            profile,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()

            return Response(
                UserSerializer(request.user).data,
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleLoginView(APIView):
    """POST /api/auth/google/"""

    def post(self, request):
        id_token = request.data.get("id_token")

        if not id_token:
            return Response(
                {"error": "id_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decoded_token = firebase_auth.verify_id_token(id_token)

            email = decoded_token.get("email")
            name = decoded_token.get("name", "")

            if not email:
                return Response(
                    {"error": "Google account has no email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Avoid get_or_create(email=email), because duplicate emails
            # can already exist and would crash with MultipleObjectsReturned.
            user = (
                User.objects
                .filter(email=email)
                .order_by("id")
                .first()
            )

            if user is None:
                user = User.objects.create(
                    username=get_unique_username_from_email(email),
                    email=email,
                    first_name=name,
                )
                user.set_unusable_password()
                user.save()

            return Response(build_auth_response(user), status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LogoutView(APIView):
    """POST /api/auth/logout/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")

            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logged out"}, status=status.HTTP_200_OK)

        except Exception:
            return Response(
                {"error": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
# ---------------------------deleted code---------------------------
class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete()
        return Response(
            {"message": "Account deleted successfully"},
            status=status.HTTP_200_OK,
        )            


class MeView(APIView):
    """GET /api/auth/me/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)