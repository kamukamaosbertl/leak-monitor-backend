from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


# ───────────────────────────────────────────────────────────
# 📝 REGISTER SERIALIZER
# ───────────────────────────────────────────────────────────
class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles user registration.

    IMPORTANT:
    - We do NOT ask for role here anymore
    - Role will be set later in profile setup
    """

    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        """
        Create a new user.

        Profile is automatically created by signals.
        Default role will remain 'technician' until profile setup.
        """
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )

        return user


# ───────────────────────────────────────────────────────────
# 👤 USER SERIALIZER (READ DATA)
# ───────────────────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    """
    Returns full user profile data.

    Used after:
    - login
    - register
    - /me endpoint
    """

    role = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    profile_completed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'role',
            'phone_number',
            'department',
            'profile_completed',
        ]

    def get_role(self, obj):
        """
        Get role from profile.
        """
        if hasattr(obj, "profile"):
            return obj.profile.role
        return None

    def get_phone_number(self, obj):
        """
        Get phone number from profile.
        """
        if hasattr(obj, "profile"):
            return obj.profile.phone_number
        return None

    def get_department(self, obj):
        """
        Get department from profile.
        """
        if hasattr(obj, "profile"):
            return obj.profile.department
        return None

    def get_profile_completed(self, obj):
        """
        Determines if profile setup is finished.

        Profile is considered complete when:
        - phone number exists
        - department exists
        - role exists
        """
        if hasattr(obj, "profile"):
            profile = obj.profile
            return bool(
                profile.phone_number and
                profile.department and
                profile.role
            )
        return False


# ───────────────────────────────────────────────────────────
# 🛠 PROFILE SETUP / UPDATE SERIALIZER
# ───────────────────────────────────────────────────────────
class ProfileSetupSerializer(serializers.ModelSerializer):
    """
    Used to complete user profile after signup.

    This matches your Flutter screens:
    - name
    - phone
    - department
    - role
    """

    class Meta:
        model = UserProfile
        fields = [
            'role',
            'phone_number',
            'department',
        ]

    def update(self, instance, validated_data):
        """
        Update profile fields.
        """
        instance.role = validated_data.get('role', instance.role)
        instance.phone_number = validated_data.get('phone_number', instance.phone_number)
        instance.department = validated_data.get('department', instance.department)

        instance.save()
        return instance