from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken

from firebase_admin import auth as firebase_auth

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ProfileSetupSerializer,   # ✅ NEW
)


# ───────────────────────────────────────────────────────────
# 🔐 JWT TOKEN GENERATION
# ───────────────────────────────────────────────────────────
def get_tokens_for_user(user):
    """
    Generates JWT access and refresh tokens.
    """
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


# ───────────────────────────────────────────────────────────
# 📦 AUTH RESPONSE BUILDER
# ───────────────────────────────────────────────────────────
def build_auth_response(user):
    """
    Standard login/register response.
    """
    return {
        "user": UserSerializer(user).data,
        "tokens": get_tokens_for_user(user),
    }


# ───────────────────────────────────────────────────────────
# 📝 REGISTER
# ───────────────────────────────────────────────────────────
class RegisterView(APIView):
    """
    POST /api/auth/register/

    Creates user WITHOUT profile completion.
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


# ───────────────────────────────────────────────────────────
# 🔑 LOGIN
# ───────────────────────────────────────────────────────────
class LoginView(APIView):
    """
    POST /api/auth/login/

    Supports username OR email.
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

        return Response(build_auth_response(user))


# ───────────────────────────────────────────────────────────
# 🛠 PROFILE SETUP (🔥 NEW)
# ───────────────────────────────────────────────────────────
class ProfileSetupView(APIView):
    """
    PUT /api/auth/profile/setup/

    Completes user profile after signup.

    This is triggered by your Flutter setup screens.
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
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ───────────────────────────────────────────────────────────
# 🔐 GOOGLE LOGIN
# ───────────────────────────────────────────────────────────
class GoogleLoginView(APIView):
    """
    POST /api/auth/google/
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

            return Response(build_auth_response(user))

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ───────────────────────────────────────────────────────────
# 🚪 LOGOUT
# ───────────────────────────────────────────────────────────
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logged out"})

        except Exception:
            return Response({"error": "Invalid token"})


# ───────────────────────────────────────────────────────────
# 👤 CURRENT USER
# ───────────────────────────────────────────────────────────
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)