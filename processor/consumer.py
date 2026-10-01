import json
import time
from datetime import datetime, timezone

import redis
import psycopg2
import os


# ============================================================
# Configuration
# ============================================================

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

REDIS_STREAM = "telemetry_raw"
CONSUMER_GROUP = "telemetry_processors"
CONSUMER_NAME = "processor_1"

POSTGRES_HOST = os.getenv("DB_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("DB_PORT", "5432"))
POSTGRES_DB = os.getenv("DB_NAME", "fleet_db")
POSTGRES_USER = os.getenv("DB_USER", "fleet_user")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD", "fleet_password")


# ============================================================
# Connections
# ============================================================

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

db = psycopg2.connect(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    database=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD
)

db.autocommit = True


# ============================================================
# Redis Consumer Group
# ============================================================

def create_consumer_group():

    try:
        redis_client.xgroup_create(
            name=REDIS_STREAM,
            groupname=CONSUMER_GROUP,
            id="0",
            mkstream=True
        )

        print(
            f"Consumer group created: {CONSUMER_GROUP}"
        )

    except redis.exceptions.ResponseError as e:

        if "BUSYGROUP" in str(e):
            print(
                f"Consumer group already exists: "
                f"{CONSUMER_GROUP}"
            )
        else:
            raise


# ============================================================
# OEM Normalization
# ============================================================

def normalize_event(payload):

    oem = payload.get("oem")

    if oem == "OEM_A":

        return {
            "event_id": payload["event_id"],
            "vehicle_vin": payload["vehicle_id"],
            "timestamp": payload["ts"],
            "speed_kmh": float(payload["spd"]),
            "engine_temp": float(payload["temp"]),
            "battery_pct": float(payload["battery"]),
            "latitude": float(payload["lat"]),
            "longitude": float(payload["lon"]),
            "oem": "OEM_A"
        }

    elif oem == "OEM_B":

        return {
            "event_id": payload["eventId"],
            "vehicle_vin": payload["vehicleId"],
            "timestamp": payload["timestamp"],
            "speed_kmh": float(payload["speedKmh"]),
            "engine_temp": float(
                payload["engineTemperature"]
            ),
            "battery_pct": float(
                payload["batteryPercentage"]
            ),
            "latitude": float(payload["latitude"]),
            "longitude": float(payload["longitude"]),
            "oem": "OEM_B"
        }

    else:
        raise ValueError(f"Unknown OEM: {oem}")


# ============================================================
# Vehicle Lookup / Creation
# ============================================================

def get_or_create_vehicle(vehicle_vin, oem):

    cursor = db.cursor()

    cursor.execute(
        """
        SELECT vehicle_id
        FROM vehicle
        WHERE vin = %s
        """,
        (vehicle_vin,)
    )

    result = cursor.fetchone()

    if result:
        vehicle_id = result[0]
        cursor.close()
        return vehicle_id

    cursor.execute(
        """
        INSERT INTO vehicle (
            vin,
            oem,
            model
        )
        VALUES (%s, %s, %s)
        RETURNING vehicle_id
        """,
        (
            vehicle_vin,
            oem,
            "Simulated Vehicle"
        )
    )

    vehicle_id = cursor.fetchone()[0]

    cursor.close()

    return vehicle_id


# ============================================================
# Duplicate Detection
# ============================================================

def is_duplicate(event_id):

    cursor = db.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM vehicle_telemetry
        WHERE event_id = %s
        LIMIT 1
        """,
        (event_id,)
    )

    result = cursor.fetchone()

    cursor.close()

    return result is not None


# ============================================================
# Out-of-Order Detection
# ============================================================

def is_out_of_order(vehicle_id, event_timestamp):

    cursor = db.cursor()

    cursor.execute(
        """
        SELECT event_timestamp
        FROM vehicle_telemetry
        WHERE vehicle_id = %s
        ORDER BY event_timestamp DESC
        LIMIT 1
        """,
        (vehicle_id,)
    )

    result = cursor.fetchone()

    cursor.close()

    if result is None:
        return False

    latest_timestamp = result[0]

    return event_timestamp < latest_timestamp


# ============================================================
# Incident Detection
# ============================================================

def detect_incidents(event):

    incidents = []

    temperature = event["engine_temp"]
    battery = event["battery_pct"]
    speed = event["speed_kmh"]

    # --------------------------------------------------------
    # OVERHEATING
    # --------------------------------------------------------

    if temperature > 100:

        incidents.append({
            "type": "OVERHEATING",
            "severity": "HIGH",
            "description": (
                f"Engine temperature reached "
                f"{temperature:.2f} C"
            )
        })

    # --------------------------------------------------------
    # LOW BATTERY
    # --------------------------------------------------------

    if battery < 20:

        incidents.append({
            "type": "LOW_BATTERY",
            "severity": "MEDIUM",
            "description": (
                f"Battery level dropped to "
                f"{battery:.2f}%"
            )
        })

    # --------------------------------------------------------
    # OVERHEATING + STOP
    # --------------------------------------------------------

    if temperature > 100 and speed < 5:

        incidents.append({
            "type": "OVERHEATING_STOP",
            "severity": "CRITICAL",
            "description": (
                "Vehicle stopped while engine "
                "temperature was above 100 C"
            )
        })

    return incidents


# ============================================================
# Vehicle Health Score
# ============================================================

def calculate_health_score(event):

    battery = event["battery_pct"]
    temperature = event["engine_temp"]
    speed = event["speed_kmh"]

    score = 100

    # Battery impact
    if battery < 20:
        score -= 35
    elif battery < 50:
        score -= 20
    elif battery < 80:
        score -= 10

    # Temperature impact
    if temperature > 100:
        score -= 30
    elif temperature > 90:
        score -= 15

    # Critical overheating + stopped vehicle
    if temperature > 100 and speed < 5:
        score -= 20

    return max(0, min(100, score))


def update_vehicle_health(vehicle_id, health_score):

    cursor = db.cursor()

    cursor.execute(
        """
        UPDATE vehicle
        SET health_score = %s
        WHERE vehicle_id = %s
        """,
        (
            health_score,
            vehicle_id
        )
    )

    cursor.close()
# ============================================================
# Save Telemetry
# ============================================================

def save_telemetry(vehicle_id, event):

    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO vehicle_telemetry (
            vehicle_id,
            event_id,
            event_timestamp,
            latitude,
            longitude,
            speed_kmh,
            engine_temp,
            battery_pct
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (event_id) DO NOTHING
        """,
        (
            vehicle_id,
            event["event_id"],
            event["timestamp"],
            event["latitude"],
            event["longitude"],
            event["speed_kmh"],
            event["engine_temp"],
            event["battery_pct"]
        )
    )

    cursor.close()


# ============================================================
# Save Incident
# ============================================================

def save_incident(vehicle_id, event, incident):

    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO incident (
            vehicle_id,
            incident_type,
            severity,
            description,
            event_timestamp,
            latitude,
            longitude
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            vehicle_id,
            incident["type"],
            incident["severity"],
            incident["description"],
            event["timestamp"],
            event["latitude"],
            event["longitude"]
        )
    )

    cursor.close()


# ============================================================
# Process One Event
# ============================================================

def process_event(message_id, fields):

    raw_data = fields.get("data")

    if not raw_data:
        return False, False, False

    payload = json.loads(raw_data)

    event = normalize_event(payload)

    event_id = event["event_id"]

    # --------------------------------------------------------
    # Duplicate check
    # --------------------------------------------------------

    if is_duplicate(event_id):

        return True, True, False

    # --------------------------------------------------------
    # Vehicle lookup
    # --------------------------------------------------------

    vehicle_id = get_or_create_vehicle(
        event["vehicle_vin"],
        event["oem"]
    )

    # --------------------------------------------------------
    # Parse timestamp
    # --------------------------------------------------------

    event_timestamp = datetime.fromisoformat(
        event["timestamp"]
    )

    # Convert timezone-aware timestamp to naive UTC
    # because PostgreSQL column is TIMESTAMP WITHOUT TIME ZONE

    if event_timestamp.tzinfo is not None:

        event_timestamp = event_timestamp.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    event["timestamp"] = event_timestamp

    # --------------------------------------------------------
    # Out-of-order check
    # --------------------------------------------------------

    out_of_order = is_out_of_order(
        vehicle_id,
        event_timestamp
    )

    # --------------------------------------------------------
    # Save telemetry
    # --------------------------------------------------------

    save_telemetry(
        vehicle_id,
        event
    )

        # --------------------------------------------------------
    # Calculate vehicle health
    # --------------------------------------------------------

    health_score = calculate_health_score(event)

    update_vehicle_health(
        vehicle_id,
        health_score
    )

    # --------------------------------------------------------
    # Detect incidents
    # --------------------------------------------------------

    incidents = detect_incidents(event)

    for incident in incidents:

        save_incident(
            vehicle_id,
            event,
            incident
        )

# ============================================================
# Main Consumer Loop
# ============================================================

def main():

    print("========================================")
    print(" Fleet Telemetry Stream Processor")
    print("========================================")

    create_consumer_group()

    processed = 0
    duplicates = 0
    out_of_order = 0
    incidents_detected = 0

    print("Processor started...")
    print("Waiting for telemetry events...")

    while True:

        try:

            messages = redis_client.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={
                    REDIS_STREAM: ">"
                },
                count=100,
                block=2000
            )

            if not messages:
                continue

            for stream_name, stream_messages in messages:

                for message_id, fields in stream_messages:

                    try:

                        processed_event, is_dup, is_ooo = (
                            process_event(
                                message_id,
                                fields
                            )
                        )

                        if is_dup:

                            duplicates += 1

                        else:

                            processed += 1

                            if is_ooo:
                                out_of_order += 1

                        redis_client.xack(
                            REDIS_STREAM,
                            CONSUMER_GROUP,
                            message_id
                        )

                    except Exception as event_error:

                        print(
                            f"Error processing "
                            f"{message_id}: "
                            f"{event_error}"
                        )

                        # Acknowledge malformed events so
                        # the test processor does not get stuck.

                        redis_client.xack(
                            REDIS_STREAM,
                            CONSUMER_GROUP,
                            message_id
                        )

        except KeyboardInterrupt:

            print("\nProcessor stopped.")

            break

        except Exception as error:

            print(
                f"Processor error: {error}"
            )

            time.sleep(2)

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if processed > 0 and processed % 1000 == 0:

            print(
                f"processed={processed} "
                f"duplicates={duplicates} "
                f"out_of_order={out_of_order}"
            )


if __name__ == "__main__":
    main()
