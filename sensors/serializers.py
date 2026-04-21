from rest_framework import serializers
from .models import LeakEvent, Alert, AlertSettings


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