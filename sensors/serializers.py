from rest_framework import serializers
from .models import (
    LeakEvent,
    Alert,
    AlertSettings,
    AlertResponse,
    MaintenanceRequest,
)


class LeakEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeakEvent
        fields = '__all__'


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = [
            'id',
            'device_id',
            'title',
            'message',
            'location',
            'severity',
            'is_read',
            'is_dismissed',
            'timestamp',
            'created_at',
        ]


class AlertSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertSettings
        fields = [
            'id',
            'delta_threshold',
            'water_lost_threshold',
            'duration_threshold',
            'updated_at',
        ]


# 🔥 NEW: Alert Response Serializer
class AlertResponseSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()  # shows username instead of ID

    class Meta:
        model = AlertResponse
        fields = [
            'id',
            'alert',
            'user',
            'action',
            'notes',
            'created_at',
        ]


# 🔥 NEW: Maintenance Request Serializer
class MaintenanceRequestSerializer(serializers.ModelSerializer):
    requested_by = serializers.StringRelatedField()

    class Meta:
        model = MaintenanceRequest
        fields = [
            'id',
            'device_id',
            'location',
            'requested_by',
            'reason',
            'severity',
            'status',
            'created_at',
        ]