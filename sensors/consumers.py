import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from firebase_admin import messaging


class SensorConsumer(AsyncWebsocketConsumer):
    group_name = 'sensors_live'
    COST_PER_LITRE = 0.0005
    MAX_HISTORY_RECORDS = 100
    HISTORY_DEDUP_WINDOW_MINUTES = 5
    HISTORY_FULL_ALERT_COOLDOWN_MINUTES = 10

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

            delta = round(flow_in - flow_out, 2)
            data['delta'] = delta

            if delta > 0:
                water_lost = round(delta * duration_minutes, 2)
                money_lost = round(water_lost * self.COST_PER_LITRE, 4)
            else:
                water_lost = 0.0
                money_lost = 0.0

            data['water_lost'] = water_lost
            data['money_lost'] = money_lost

            thresholds = await self.get_alert_settings()
            delta_threshold = thresholds['delta']
            water_threshold = thresholds['water']
            duration_threshold = thresholds['duration']

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

            if data['status'] in ['leak_detected', 'critical']:
                history_result = await self.save_leak_event(data)

                if history_result.get('history_full_notified'):
                    await self.send_push_notification(
                        'History Limit Reached',
                        'History is full (100 records). Old records are being replaced automatically.',
                        data={
                            'type': 'history_limit',
                            'severity': 'info',
                            'device_id': str(data.get('device_id', 'unknown')),
                            'location': str(data.get('location', 'Unknown')),
                        }
                    )

                alert_data = await self.create_alert_if_needed(data)

                if alert_data:
                    await self.send_push_notification(
                        alert_data['title'],
                        alert_data['message'],
                        data={
                            'type': 'water_leak',
                            'alert_id': str(alert_data['alert_id']),
                            'severity': str(alert_data['severity']),
                            'device_id': str(alert_data['device_id']),
                            'location': str(alert_data['location']),
                        }
                    )

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
        from .models import LeakEvent, Alert

        device_id = data.get('device_id', 'unknown')
        location = data.get('location', 'Unknown')
        status_value = data.get('status', 'normal')

        recent_cutoff = timezone.now() - timedelta(
            minutes=self.HISTORY_DEDUP_WINDOW_MINUTES
        )

        duplicate_exists = LeakEvent.objects.filter(
            device_id=device_id,
            location=location,
            status=status_value,
            created_at__gte=recent_cutoff,
        ).exists()

        if duplicate_exists:
            return {
                'saved': False,
                'reason': 'duplicate_recent_event',
                'history_full': False,
                'history_full_notified': False,
            }

        current_count = LeakEvent.objects.count()
        history_full = current_count >= self.MAX_HISTORY_RECORDS
        history_full_notified = False

        if history_full:
            alert_cutoff = timezone.now() - timedelta(
                minutes=self.HISTORY_FULL_ALERT_COOLDOWN_MINUTES
            )

            already_notified = Alert.objects.filter(
                title='History Limit Reached',
                created_at__gte=alert_cutoff,
            ).exists()

            if not already_notified:
                Alert.objects.create(
                    device_id=device_id,
                    title='History Limit Reached',
                    message='History is full (100 records). Old records are being replaced automatically.',
                    location=location,
                    severity='info',
                    timestamp=timezone.now(),
                )
                history_full_notified = True

            oldest = LeakEvent.objects.order_by('created_at').first()
            if oldest:
                oldest.delete()

        LeakEvent.objects.create(
            device_id=device_id,
            flow_in=float(data.get('flow_in', 0)),
            flow_out=float(data.get('flow_out', 0)),
            delta=float(data.get('delta', 0)),
            duration_minutes=float(data.get('duration_minutes', 0)),
            water_lost=float(data.get('water_lost', 0)),
            money_lost=float(data.get('money_lost', 0)),
            location=location,
            status=status_value,
            timestamp=parse_datetime(data.get('timestamp', '')) or timezone.now(),
        )

        return {
            'saved': True,
            'reason': 'created',
            'history_full': history_full,
            'history_full_notified': history_full_notified,
        }

    @database_sync_to_async
    def create_alert_if_needed(self, data):
        from django.utils import timezone
        from .models import Alert

        status_value = data.get('status', 'normal')
        device_id = data.get('device_id', 'unknown')
        location = data.get('location', 'Unknown')

        if status_value == 'critical':
            severity = 'critical'
            title = 'Critical Leak Detected'
        elif status_value == 'leak_detected':
            severity = 'warning'
            title = 'Leak Detected'
        else:
            return None

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
            return None

        alert = Alert.objects.create(
            device_id=device_id,
            title=title,
            message=message,
            location=location,
            severity=severity,
            timestamp=timezone.now(),
        )

        return {
            'alert_id': alert.id,
            'title': alert.title,
            'message': alert.message,
            'severity': alert.severity,
            'device_id': alert.device_id,
            'location': alert.location,
        }

    @database_sync_to_async
    def get_active_device_tokens(self):
        from .models import DeviceToken

        return list(
            DeviceToken.objects.filter(is_active=True).values_list('token', flat=True)
        )

    async def send_push_notification(self, title, body, data=None):
        tokens = await self.get_active_device_tokens()

        for token in tokens:
            try:
                msg = messaging.Message(
                    token=token,
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=data or {},
                )
                messaging.send(msg)
                print(f'Push sent to {token}')
            except Exception as e:
                print(f'Push failed for {token}: {e}')