import json
import random
import time
import uuid
from datetime import datetime, timezone

import redis


# -----------------------------
# Configuration
# -----------------------------

REDIS_HOST = "localhost"
REDIS_PORT = 6379
STREAM_NAME = "telemetry_raw"

VEHICLE_COUNT = 100_000


# -----------------------------
# Redis connection
# -----------------------------

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)


# -----------------------------
# Vehicle ID generator
# -----------------------------

def vehicle_id(number):
    return f"VH{number:06d}"


# -----------------------------
# Generate canonical telemetry
# -----------------------------

def generate_vehicle_data(number):
    vin = vehicle_id(number)

    speed = round(random.uniform(0, 120), 2)
    temperature = round(random.uniform(70, 110), 2)
    battery = round(random.uniform(10, 100), 2)

    latitude = round(random.uniform(12.90, 13.15), 6)
    longitude = round(random.uniform(80.15, 80.35), 6)

    return {
        "event_id": str(uuid.uuid4()),
        "vehicle_id": vin,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "speed_kmh": speed,
        "engine_temp": temperature,
        "battery_pct": battery,
        "latitude": latitude,
        "longitude": longitude
    }


# -----------------------------
# Convert telemetry to OEM A
# -----------------------------

def to_oem_a(data):
    return {
        "event_id": data["event_id"],
        "vehicle_id": data["vehicle_id"],
        "ts": data["timestamp"],
        "spd": data["speed_kmh"],
        "temp": data["engine_temp"],
        "battery": data["battery_pct"],
        "lat": data["latitude"],
        "lon": data["longitude"]
    }


# -----------------------------
# Convert telemetry to OEM B
# -----------------------------

def to_oem_b(data):
    return {
        "eventId": data["event_id"],
        "vehicleId": data["vehicle_id"],
        "timestamp": data["timestamp"],
        "speedKmh": data["speed_kmh"],
        "engineTemperature": data["engine_temp"],
        "batteryPercentage": data["battery_pct"],
        "latitude": data["latitude"],
        "longitude": data["longitude"]
    }


# -----------------------------
# Main simulator
# -----------------------------

def main():

    print("Starting Fleet Vehicle Simulator...")
    print(f"Vehicles configured: {VEHICLE_COUNT}")
    print(f"Redis Stream: {STREAM_NAME}")

    event_count = 0

    while True:

        # Generate a batch of vehicles per iteration
        for number in range(1, VEHICLE_COUNT + 1):

            data = generate_vehicle_data(number)

            # Randomly simulate different OEM formats
            if random.random() < 0.5:
                payload = to_oem_a(data)
                payload["oem"] = "OEM_A"
            else:
                payload = to_oem_b(data)
                payload["oem"] = "OEM_B"

            # Add event to Redis Stream
            r.xadd(
                STREAM_NAME,
                {
                    "data": json.dumps(payload)
                }
            )

            event_count += 1

            # Print progress
            if event_count % 1000 == 0:
                print(f"Events generated: {event_count}")

        # Small delay before next cycle
        time.sleep(1)


if __name__ == "__main__":
    main()
