import json
from datetime import timedelta

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class SensorConsumer(AsyncWebsocketConsumer):
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

            # Load thresholds from DB
            thresholds = await self.get_alert_settings()
            delta_threshold = thresholds['delta']
            water_threshold = thresholds['water']
            duration_threshold = thresholds['duration']

            # Corrected status logic:
            #
            # normal:
            #   delta below the configured delta threshold
            #
            # leak_detected:
            #   any configured threshold is crossed
            #
            # critical:
            #   severe case = much higher than threshold
            #
            # This keeps the behavior predictable and makes the
            # saved settings actually control the system.
            if (
                delta >= (delta_threshold * 2)
                or water_lost >= (water_threshold * 2)
                or duration_minutes >= (duration_threshold * 2)
            ):
                data['status'] = 'critical'
            elif (
                delta >= delta_threshold
                or water_lost >= water_threshold
                or duration_minutes >= duration_threshold
            ):
                data['status'] = 'leak_detected'
            else:
                data['status'] = 'normal'

            # Save leak events and create alerts only for leak states
            if data['status'] in ['leak_detected', 'critical']:
                await self.save_leak_event(data)
                await self.create_alert_if_needed(data)

            # Broadcast to all connected clients
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'sensor_update',
                    'data': data
                }
            )

            print(
                f"Processed | device={data.get('device_id')} | "
                f"location={data.get('location')} | "
                f"delta={delta} | water_lost={water_lost} | "
                f"duration={duration_minutes} | status={data['status']} | "
                f"thresholds(delta={delta_threshold}, water={water_threshold}, duration={duration_threshold})"
            )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON received'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': f'Processing failed: {str(e)}'
            }))

    async def sensor_update(self, event):
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def get_alert_settings(self):
        from .models import AlertSettings

        settings_obj, _ = AlertSettings.objects.get_or_create(id=1)

        return {
            'delta': settings_obj.delta_threshold,
            'water': settings_obj.water_lost_threshold,
            'duration': settings_obj.duration_threshold,
        }

    @database_sync_to_async
    def save_leak_event(self, data):
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

    @database_sync_to_async
    def create_alert_if_needed(self, data):
        from django.utils import timezone
        from .models import Alert

        status = data.get('status', 'normal')
        device_id = data.get('device_id', 'unknown')
        location = data.get('location', 'Unknown')

        if status == 'critical':
            severity = 'critical'
            title = 'Critical Leak Detected'
        elif status == 'leak_detected':
            severity = 'warning'
            title = 'Leak Detected'
        else:
            return

        message = (
            f"{title} at {location}. "
            f"Delta: {data.get('delta')} L/min, "
            f"water lost: {data.get('water_lost')} L."
        )

        recent_cutoff = timezone.now() - timedelta(minutes=5)

        if Alert.objects.filter(
            device_id=device_id,
            location=location,
            severity=severity,
            created_at__gte=recent_cutoff,
            is_dismissed=False,
        ).exists():
            return

        Alert.objects.create(
            device_id=device_id,
            title=title,
            message=message,
            location=location,
            severity=severity,
            timestamp=timezone.now(),
        )