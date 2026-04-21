import json
from datetime import timedelta

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class SensorConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for live sensor data.

    Current responsibilities:
    - ESP32 sends sensor data
    - Django calculates delta, water loss, money loss, and status
    - Django saves leak events when needed
    - Django creates alerts for leak_detected and critical states
    - Django broadcasts live updates to all connected Flutter apps
    """

    group_name = 'sensors_live'
    COST_PER_LITRE = 0.0005

    async def connect(self):
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        print(f'Client connected: {self.channel_name}')

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        print(f'Client disconnected: {self.channel_name}')

    async def receive(self, text_data):
        """
        Expected ESP32 payload:
        {
            "device_id": "esp32_001",
            "flow_in": 12.5,
            "flow_out": 5.0,
            "duration_minutes": 3,
            "location": "Kitchen",
            "timestamp": "2026-04-15T10:00:00Z"
        }
        """
        try:
            data = json.loads(text_data)

            flow_in = float(data.get('flow_in', 0))
            flow_out = float(data.get('flow_out', 0))
            duration_minutes = float(data.get('duration_minutes', 0))

            # Calculate delta
            delta = round(flow_in - flow_out, 2)
            data['delta'] = delta

            # Calculate water lost and money lost
            if delta > 0:
                water_lost = round(delta * duration_minutes, 2)
                money_lost = round(water_lost * self.COST_PER_LITRE, 4)
            else:
                water_lost = 0.0
                money_lost = 0.0

            data['water_lost'] = water_lost
            data['money_lost'] = money_lost

            # Determine status
            if delta < 2.0:
                data['status'] = 'normal'
            elif delta < 5.0:
                data['status'] = 'warning'
            elif delta < 10.0:
                data['status'] = 'leak_detected'
            else:
                data['status'] = 'critical'

            # Save leak history only for real leak states
            if data['status'] in ['leak_detected', 'critical']:
                await self.save_leak_event(data)
                await self.create_alert_if_needed(data)

            # Broadcast live update to all connected clients
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'sensor_update',
                    'data': data
                }
            )

            print(
                f"Data processed — location: {data.get('location')} | "
                f"flow_in: {flow_in} | flow_out: {flow_out} | "
                f"delta: {delta} | water_lost: {water_lost}L | "
                f"money_lost: ${money_lost} | status: {data['status']}"
            )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON received — expected valid JSON format'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': f'Processing failed: {str(e)}'
            }))

    async def sensor_update(self, event):
        """
        Delivers broadcast data to one connected client.
        """
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def save_leak_event(self, data):
        """
        Saves leak history records to the database.
        """
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime
        from .models import LeakEvent

        LeakEvent.objects.create(
            device_id=data.get('device_id', 'unknown'),
            flow_in=data.get('flow_in', 0),
            flow_out=data.get('flow_out', 0),
            delta=data.get('delta', 0),
            duration_minutes=data.get('duration_minutes', 0),
            water_lost=data.get('water_lost', 0),
            money_lost=data.get('money_lost', 0),
            location=data.get('location', 'Unknown'),
            status=data.get('status', 'normal'),
            timestamp=parse_datetime(data.get('timestamp', '')) or timezone.now(),
        )

        print(
            f"Leak event saved — location: {data.get('location')} | "
            f"delta: {data.get('delta')} | "
            f"water_lost: {data.get('water_lost')}L | "
            f"money_lost: ${data.get('money_lost')}"
        )

    @database_sync_to_async
    def create_alert_if_needed(self, data):
        """
        Creates an alert for leak_detected or critical states.

        To avoid spamming alerts every second, this checks whether
        a similar alert for the same device/location/severity was
        created recently.
        """
        from django.utils import timezone
        from .models import Alert

        status = data.get('status', 'normal')
        device_id = data.get('device_id', 'unknown')
        location = data.get('location', 'Unknown')

        # Map leak status to alert severity
        if status == 'critical':
            severity = 'critical'
            title = 'Critical Leak Detected'
            message = (
                f"Critical water loss detected at {location}. "
                f"Delta: {data.get('delta', 0)} L/min, "
                f"water lost: {data.get('water_lost', 0)} L."
            )
        elif status == 'leak_detected':
            severity = 'warning'
            title = 'Leak Detected'
            message = (
                f"Leak detected at {location}. "
                f"Delta: {data.get('delta', 0)} L/min, "
                f"water lost: {data.get('water_lost', 0)} L."
            )
        else:
            return

        # Prevent duplicate alerts in a short window
        recent_cutoff = timezone.now() - timedelta(minutes=5)

        already_exists = Alert.objects.filter(
            device_id=device_id,
            location=location,
            severity=severity,
            created_at__gte=recent_cutoff,
            is_dismissed=False,
        ).exists()

        if already_exists:
            print(
                f"Skipped duplicate alert — device: {device_id} | "
                f"location: {location} | severity: {severity}"
            )
            return

        Alert.objects.create(
            device_id=device_id,
            title=title,
            message=message,
            location=location,
            severity=severity,
            timestamp=timezone.now(),
        )

        print(
            f"Alert created — device: {device_id} | "
            f"location: {location} | severity: {severity}"
        )