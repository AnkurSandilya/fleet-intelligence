import json
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

import redis


# ============================================================
# Configuration
# ============================================================

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

STREAM_NAME = "telemetry_raw"

# Default: 100,000 vehicles
# Example:
# VEHICLE_COUNT=100 python simulator/simulator.py
VEHICLE_COUNT = int(os.getenv("VEHICLE_COUNT", "100000"))

# Events generated per vehicle in each cycle
EVENTS_PER_VEHICLE = int(
    os.getenv("EVENTS_PER_VEHICLE", "1")
)

# Duplicate event probability
DUPLICATE_RATE = float(
    os.getenv("DUPLICATE_RATE", "0.02")
)

# Out-of-order event probability
OUT_OF_ORDER_RATE = float(
    os.getenv("OUT_OF_ORDER_RATE", "0.02")
)

# If true, simulator runs one cycle and exits.
# If false, simulator keeps running.
RUN_ONCE = (
    os.getenv("RUN_ONCE", "false").lower() == "true"
)


# ============================================================
# Redis Connection
# ============================================================

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)


# ============================================================
# Vehicle ID
# ============================================================

def vehicle_id(number):
    return f"VH{number:06d}"


# ============================================================
# Generate Canonical Telemetry
# ============================================================

def generate_vehicle_data(number, event_time=None):

    vin = vehicle_id(number)

    if event_time is None:
        event_time = datetime.now(timezone.utc)

    speed = round(
        random.uniform(0, 120),
        2
    )

    temperature = round(
        random.uniform(70, 110),
        2
    )

    battery = round(
        random.uniform(10, 100),
        2
    )

    latitude = round(
        random.uniform(12.90, 13.15),
        6
    )

    longitude = round(
        random.uniform(80.15, 80.35),
        6
    )

    return {
        "event_id": str(uuid.uuid4()),
        "vehicle_id": vin,
        "timestamp": event_time.isoformat(),
        "speed_kmh": speed,
        "engine_temp": temperature,
        "battery_pct": battery,
        "latitude": latitude,
        "longitude": longitude
    }


# ============================================================
# OEM A Format
# ============================================================

def to_oem_a(data):

    return {
        "event_id": data["event_id"],
        "vehicle_id": data["vehicle_id"],
        "ts": data["timestamp"],
        "spd": data["speed_kmh"],
        "temp": data["engine_temp"],
        "battery": data["battery_pct"],
        "lat": data["latitude"],
        "lon": data["longitude"],
        "oem": "OEM_A"
    }


# ============================================================
# OEM B Format
# ============================================================

def to_oem_b(data):

    return {
        "eventId": data["event_id"],
        "vehicleId": data["vehicle_id"],
        "timestamp": data["timestamp"],
        "speedKmh": data["speed_kmh"],
        "engineTemperature": data["engine_temp"],
        "batteryPercentage": data["battery_pct"],
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "oem": "OEM_B"
    }


# ============================================================
# Generate OEM Event
# ============================================================

def generate_event(number, event_time=None):

    data = generate_vehicle_data(
        number,
        event_time
    )

    if random.random() < 0.5:
        return to_oem_a(data)

    return to_oem_b(data)


# ============================================================
# Push Event to Redis Stream
# ============================================================

def push_event(payload):

    redis_client.xadd(
        STREAM_NAME,
        {
            "data": json.dumps(payload)
        }
    )


# ============================================================
# Main Simulator
# ============================================================

def main():

    print("========================================")
    print(" Fleet Vehicle Simulator")
    print("========================================")
    print(f"Vehicles       : {VEHICLE_COUNT}")
    print(f"Events/vehicle : {EVENTS_PER_VEHICLE}")
    print(f"Redis Stream   : {STREAM_NAME}")
    print(f"Duplicate rate : {DUPLICATE_RATE}")
    print(f"Out-of-order   : {OUT_OF_ORDER_RATE}")
    print(f"Run once       : {RUN_ONCE}")
    print("========================================")

    event_count = 0
    duplicate_count = 0
    out_of_order_count = 0

    while True:

        for number in range(
            1,
            VEHICLE_COUNT + 1
        ):

            for _ in range(EVENTS_PER_VEHICLE):

                current_time = datetime.now(
                    timezone.utc
                )

                # Generate normal event
                payload = generate_event(
                    number,
                    current_time
                )

                push_event(payload)

                event_count += 1

                # --------------------------------------------
                # Duplicate event
                # --------------------------------------------

                if random.random() < DUPLICATE_RATE:

                    push_event(payload)

                    duplicate_count += 1

                # --------------------------------------------
                # Out-of-order event
                # --------------------------------------------

                if random.random() < OUT_OF_ORDER_RATE:

                    old_time = (
                        current_time
                        - timedelta(
                            seconds=random.randint(
                                1,
                                30
                            )
                        )
                    )

                    old_payload = generate_event(
                        number,
                        old_time
                    )

                    push_event(old_payload)

                    out_of_order_count += 1

                # --------------------------------------------
                # Progress logging
                # --------------------------------------------

                if event_count % 1000 == 0:

                    print(
                        f"events={event_count} "
                        f"duplicates={duplicate_count} "
                        f"out_of_order={out_of_order_count}"
                    )

        # --------------------------------------------
        # One-cycle mode
        # --------------------------------------------

        if RUN_ONCE:

            print("========================================")
            print(" One cycle completed")
            print(f" Normal events  : {event_count}")
            print(f" Duplicates     : {duplicate_count}")
            print(
                f" Out-of-order   : "
                f"{out_of_order_count}"
            )
            print("========================================")

            break

        # Continuous mode
        time.sleep(1)


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()
