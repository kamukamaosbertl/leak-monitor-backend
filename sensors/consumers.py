import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async  # allows database calls inside async code


class SensorConsumer(AsyncWebsocketConsumer):
    """
    This is the WebSocket brain of the system.
    
    It handles three types of connections:
    - ESP32 connects and streams live sensor data every 1 second
    - Flutter app connects and receives live data in real time
    - When a leak is detected, it automatically saves to the database
    """

    # All connected clients (ESP32 and Flutter) join this one group
    # so when ESP32 sends data, ALL Flutter apps receive it instantly
    group_name = 'sensors_live'

    # Cost of water per litre in USD
    # Uganda water cost ≈ 0.0005 USD per litre — adjust as needed
    COST_PER_LITRE = 0.0005

    # ─────────────────────────────────────────
    # STEP 1: Someone connects to the WebSocket
    # ─────────────────────────────────────────
    async def connect(self):
        # Add this new connection to the group
        # so it can receive broadcasts from other members
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        # without this line the connection is rejected
        await self.accept()

        print(f'Client connected: {self.channel_name}')

    # ─────────────────────────────────────────
    # STEP 2: Someone disconnects
    # ─────────────────────────────────────────
    async def disconnect(self, close_code):
        # Remove this connection from the group
        # so it no longer receives broadcasts
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

        print(f'Client disconnected: {self.channel_name}')

    # ─────────────────────────────────────────
    # STEP 3: ESP32 sends sensor data
    # ─────────────────────────────────────────
    async def receive(self, text_data):
        """
        Called every time ESP32 sends a message over WebSocket.
        
        What happens here:
        1. Parse the incoming JSON data
        2. Calculate delta (flow_in - flow_out)
        3. Calculate water_lost and money_lost automatically
        4. Determine leak status based on delta value
        5. If leak detected → save to database automatically
        6. Broadcast the complete data to all Flutter apps

        ESP32 only needs to send:
        {
            "device_id": "esp32_001",
            "flow_in": 12.5,
            "flow_out": 5.0,
            "duration_minutes": 3,
            "location": "Kitchen",
            "timestamp": "2026-04-15T10:00:00Z"
        }
        Django calculates everything else automatically.
        """
        try:
            # Parse the raw JSON string into a Python dictionary
            data = json.loads(text_data)

            # ── Get flow readings from ESP32 ─────────────────
            flow_in          = float(data.get('flow_in', 0))
            flow_out         = float(data.get('flow_out', 0))
            duration_minutes = float(data.get('duration_minutes', 0))

            # ── Calculate delta ──────────────────────────────
            # Delta = how much water is being lost per minute
            # ESP32 only sends flow_in and flow_out
            # Django calculates the difference automatically
            delta = round(flow_in - flow_out, 2)
            data['delta'] = delta

            # ── Calculate water lost and money lost ──────────
            # Water lost (litres) = delta × duration_minutes
            # Money lost (USD)    = water_lost × cost per litre
            # Only calculate if there is actually a loss (delta > 0)
            if delta > 0:
                water_lost = round(delta * duration_minutes, 2)
                money_lost = round(water_lost * self.COST_PER_LITRE, 4)
            else:
                water_lost = 0.0
                money_lost = 0.0

            data['water_lost'] = water_lost
            data['money_lost'] = money_lost

            # ── Determine leak status ────────────────────────
            # Based on the delta value we assign a status
            # These thresholds mean:
            #   delta < 2.0  → everything is normal
            #   delta < 5.0  → small difference, worth watching
            #   delta < 10.0 → significant loss, likely a leak
            #   delta >= 10  → confirmed leak, critical level
            if delta < 2.0:
                data['status'] = 'normal'
            elif delta < 5.0:
                data['status'] = 'warning'
            elif delta < 10.0:
                data['status'] = 'leak_detected'
            else:
                data['status'] = 'critical'

            # ── Auto save to database if leak detected ───────
            # If status is leak_detected or critical we save
            # a record to PostgreSQL automatically
            # This means you do NOT need the hardware guy to
            # send a separate HTTP POST — Django handles it
            if data['status'] in ['leak_detected', 'critical']:
                await self.save_leak_event(data)

            # ── Broadcast to all Flutter apps ────────────────
            # Send the complete data to every connected client
            # in the group — this is what updates the dashboard
            # in real time on every Flutter app simultaneously
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'sensor_update',  # must match method name below
                    'data': data
                }
            )

            print(f"Data processed — location: {data.get('location')} | "
                  f"flow_in: {flow_in} | flow_out: {flow_out} | "
                  f"delta: {delta} | water_lost: {water_lost}L | "
                  f"money_lost: ${money_lost} | status: {data['status']}")

        except json.JSONDecodeError:
            # If ESP32 sends badly formatted data, send back an error
            # instead of crashing the entire server
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON received — expected valid JSON format'
            }))

    # ─────────────────────────────────────────
    # STEP 4: Send data to one specific client
    # ─────────────────────────────────────────
    async def sensor_update(self, event):
        """
        Called automatically by group_send above.
        
        group_send broadcasts to the GROUP.
        This method delivers it to THIS specific client.
        Every connected Flutter app has its own version
        of this method running — so all apps get the data.
        """
        await self.send(text_data=json.dumps(event['data']))

    # ─────────────────────────────────────────
    # STEP 5: Save leak event to database
    # ─────────────────────────────────────────
    @database_sync_to_async
    def save_leak_event(self, data):
        """
        Saves a leak event record to PostgreSQL.
        
        @database_sync_to_async is required because:
        - Our WebSocket consumer runs in async mode
        - Django database calls are synchronous (blocking)
        - This decorator bridges the two safely
        
        This only runs when status is leak_detected or critical.
        It saves the location, flow readings, and timestamp
        so you have a full history of every leak that happened.
        """
        from .models import LeakEvent
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone

        LeakEvent.objects.create(
            device_id        = data.get('device_id', 'unknown'),
            flow_in          = data.get('flow_in', 0),
            flow_out         = data.get('flow_out', 0),
            delta            = data.get('delta', 0),
            duration_minutes = data.get('duration_minutes', 0),
            water_lost       = data.get('water_lost', 0),
            money_lost       = data.get('money_lost', 0),
            location         = data.get('location', 'Unknown'),
            status           = status,
            # parse the timestamp from ESP32, fall back to now if missing
            timestamp        = parse_datetime(
                                   data.get('timestamp', '')
                               ) or timezone.now(),
        )

        print(f"Leak event saved — location: {data.get('location')} | "
              f"delta: {data.get('delta')} | "
              f"water_lost: {data.get('water_lost')}L | "
              f"money_lost: ${data.get('money_lost')}")