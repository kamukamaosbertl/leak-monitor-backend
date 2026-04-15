from rest_framework import serializers
from .models import LeakEvent

class LeakEventSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeakEvent
        fields = '__all__'