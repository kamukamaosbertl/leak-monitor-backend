from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )

        # 🔥 Profile is auto-created by signals (no need to create manually)

        return user


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'role',
            'phone_number',
        ]

    def get_role(self, obj):
        if hasattr(obj, "profile"):
            return obj.profile.role
        return "worker"

    def get_phone_number(self, obj):
        if hasattr(obj, "profile"):
            return obj.profile.phone_number
        return None