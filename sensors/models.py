from django.db import models

class LeakEvent(models.Model):
    """
    Stores confirmed leak events sent by the ESP32
    via HTTP POST every 20 seconds during a leak.
    """
    device_id        = models.CharField(max_length=100)
    flow_in          = models.FloatField()
    flow_out         = models.FloatField()
    delta            = models.FloatField()
    duration_minutes = models.FloatField()
    water_lost       = models.FloatField()
    money_lost       = models.FloatField()
    status           = models.CharField(max_length=20)
    location         = models.CharField(max_length=255)
    timestamp        = models.DateTimeField()
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.device_id} - {self.location} - {self.timestamp}"