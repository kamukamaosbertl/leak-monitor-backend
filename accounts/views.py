from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken

from firebase_admin import auth as firebase_auth

from .serializers import RegisterSerializer, UserSerializer


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def get_user_role(user):
    """
    Safe role fallback.

    Later, when you add a real Profile model, this can read:
    user.profile.role

    For now:
    - superuser/staff = admin
    - normal user = worker
    """
    if user.is_superuser or user.is_staff:
        return "admin"

    if hasattr(user, "profile") and hasattr(user.profile, "role"):
        return user.profile.role

    return "worker"


def build_auth_response(user):
    user_data = UserSerializer(user).data
    user_data["role"] = get_user_role(user)

    return {
        "user": user_data,
        "tokens": get_tokens_for_user(user),
    }


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Creates normal email/password account.
    """

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
    Allows login with username or email.
    """

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "").strip()

        if not username or not password:
            return Response(
                {"error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = None

        if "@" in username:
            try:
                found_user = User.objects.get(email=username)
                user = authenticate(
                    username=found_user.username,
                    password=password,
                )
            except User.DoesNotExist:
                user = None
        else:
            user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(build_auth_response(user), status=status.HTTP_200_OK)


class GoogleLoginView(APIView):
    """
    POST /api/auth/google/

    Flutter sends Firebase ID token:
    {
        "id_token": "firebase_google_id_token"
    }

    Django verifies token, creates/fetches user, returns JWT + role.
    """

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
            uid = decoded_token.get("uid")

            if not email:
                return Response(
                    {"error": "Google account email not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            username = email.split("@")[0]

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "first_name": name,
                },
            )

            if created:
                user.set_unusable_password()
                user.save()

            return Response(
                {
                    **build_auth_response(user),
                    "firebase_uid": uid,
                    "created": created,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Google login failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists refresh token.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")

            if not refresh_token:
                return Response(
                    {"error": "refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Logged out successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception:
            return Response(
                {"error": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MeView(APIView):
    """
    GET /api/auth/me/
    Returns current user info.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_data = UserSerializer(request.user).data
        user_data["role"] = get_user_role(request.user)

        return Response(user_data, status=status.HTTP_200_OK)