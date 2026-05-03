import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from firebase_admin import messaging


class SensorConsumer(AsyncWebsocketConsumer):
    # WebSocket group name used to broadcast live sensor updates to all clients.
    group_name = 'sensors_live'

    # Cost of lost water in Ugandan Shillings per litre.
    # Change this value if your real water price per litre is different.
    COST_PER_LITRE_UGX = 5

    # Fixed delta rules for leak detection.
    # Delta means: flow_in - flow_out.
    # 0 to 5       => normal
    # greater than 5 to 10  => leak_detected
    # greater than 10       => critical
    NORMAL_DELTA_MAX = 5
    LEAK_DELTA_MAX = 10

    # Maximum number of leak history records to keep in the database.
    MAX_HISTORY_RECORDS = 100

    # Prevent saving the same leak event repeatedly within this number of minutes.
    HISTORY_DEDUP_WINDOW_MINUTES = 5

    # Prevent sending the "history full" notification too often.
    HISTORY_FULL_ALERT_COOLDOWN_MINUTES = 10

    async def connect(self):
        # Add this WebSocket connection to the live sensor group.
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Accept the WebSocket connection.
        await self.accept()
        print(f'Client connected: {self.channel_name}')

    async def disconnect(self, close_code):
        # Remove this WebSocket connection from the live sensor group.
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        print(f'Client disconnected: {self.channel_name}')

    async def receive(self, text_data):
        try:
            # Convert the incoming WebSocket JSON string into a Python dictionary.
            data = json.loads(text_data)

            # Read sensor values safely. If a value is missing, use 0.
            flow_in = float(data.get('flow_in', 0))
            flow_out = float(data.get('flow_out', 0))
            duration_minutes = float(data.get('duration_minutes', 0))

            # Delta is the difference between water entering and water leaving.
            # A positive delta means water may be getting lost.
            delta = round(flow_in - flow_out, 2)
            data['delta'] = delta

            # Calculate water lost and money lost only when delta is positive.
            if delta > 0:
                water_lost = round(delta * duration_minutes, 2)
                money_lost = round(water_lost * self.COST_PER_LITRE_UGX, 2)
            else:
                water_lost = 0.0
                money_lost = 0.0

            # Add calculated values back to the payload so frontend receives them.
            data['water_lost'] = water_lost
            data['money_lost'] = money_lost
            data['currency'] = 'UGX'

            # Fixed leak detection logic based only on delta.
            # 0 to 5 is normal.
            # Above 5 up to 10 is leak detected.
            # Above 10 is critical.
            if delta > self.LEAK_DELTA_MAX:
                data['status'] = 'critical'
            elif delta > self.NORMAL_DELTA_MAX:
                data['status'] = 'leak_detected'
            else:
                data['status'] = 'normal'

            # Only save history and send notifications for real leak cases.
            if data['status'] in ['leak_detected', 'critical']:
                history_result = await self.save_leak_event(data)

                # Notify admins/users when the history table is full.
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

                # Create a database alert if one has not already been created recently.
                alert_data = await self.create_alert_if_needed(data)

                # Send push notification only when a new alert was created.
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

            # Broadcast the processed sensor data to all connected WebSocket clients.
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'sensor_update',
                    'data': data
                }
            )

            # Backend log for debugging and monitoring.
            print(
                f"Processed | device={data.get('device_id')} | "
                f"location={data.get('location')} | "
                f"delta={delta} | water_lost={water_lost} | "
                f"money_lost=UGX {money_lost} | "
                f"duration={duration_minutes} | status={data['status']} | "
                f"fixed_delta_rules(normal=0-5, leak=>5-10, critical=>10)"
            )

        except json.JSONDecodeError:
            # Return a clear error when the incoming WebSocket message is not valid JSON.
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON received'
            }))
        except Exception as e:
            # Return a clear error for any unexpected processing failure.
            await self.send(text_data=json.dumps({
                'error': f'Processing failed: {str(e)}'
            }))

    async def sensor_update(self, event):
        # Send broadcasted sensor data to this WebSocket client.
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def save_leak_event(self, data):
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime
        from .models import LeakEvent, Alert

        # Basic leak event information.
        device_id = data.get('device_id', 'unknown')
        location = data.get('location', 'Unknown')
        status_value = data.get('status', 'normal')

        # Check whether a similar event was saved recently.
        recent_cutoff = timezone.now() - timedelta(
            minutes=self.HISTORY_DEDUP_WINDOW_MINUTES
        )

        duplicate_exists = LeakEvent.objects.filter(
            device_id=device_id,
            location=location,
            status=status_value,
            created_at__gte=recent_cutoff,
        ).exists()

        # Do not save duplicate leak events within the dedup window.
        if duplicate_exists:
            return {
                'saved': False,
                'reason': 'duplicate_recent_event',
                'history_full': False,
                'history_full_notified': False,
            }

        # Check whether leak history has reached the maximum limit.
        current_count = LeakEvent.objects.count()
        history_full = current_count >= self.MAX_HISTORY_RECORDS
        history_full_notified = False

        if history_full:
            # Avoid sending the history full alert repeatedly.
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

            # Delete the oldest history record so the newest one can be saved.
            oldest = LeakEvent.objects.order_by('created_at').first()
            if oldest:
                oldest.delete()

        # Save the leak event in the database.
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

        # Read the processed leak status and device details.
        status_value = data.get('status', 'normal')
        device_id = data.get('device_id', 'unknown')
        location = data.get('location', 'Unknown')

        # Pick alert severity and title based on the fixed delta status.
        if status_value == 'critical':
            severity = 'critical'
            title = 'Critical Leak Detected'
        elif status_value == 'leak_detected':
            severity = 'warning'
            title = 'Leak Detected'
        else:
            return None

        # Alert message shown in the app and sent through push notification.
        message = (
            f"{title} at {location}. "
            f"Delta: {data.get('delta')} L/min, "
            f"water lost: {data.get('water_lost')} L, "
            f"money lost: UGX {data.get('money_lost')}."
        )

        # Avoid creating duplicate active alerts within 5 minutes.
        recent_cutoff = timezone.now() - timedelta(minutes=5)

        if Alert.objects.filter(
            device_id=device_id,
            location=location,
            severity=severity,
            created_at__gte=recent_cutoff,
            is_dismissed=False,
        ).exists():
            return None

        # Create the alert record in the database.
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

        # Get all active Firebase device tokens for push notifications.
        return list(
            DeviceToken.objects.filter(is_active=True).values_list('token', flat=True)
        )

    async def send_push_notification(self, title, body, data=None):
        # Load active Firebase tokens from the database.
        tokens = await self.get_active_device_tokens()

        # Send the notification to each active device.
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
                # Keep processing other tokens even if one token fails.
                print(f'Push failed for {token}: {e}')
