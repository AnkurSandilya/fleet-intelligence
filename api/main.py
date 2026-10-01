from fastapi import FastAPI
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from processor.vector_search import search
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
import time
import heapq
from jose import jwt, JWTError
import os

app = FastAPI(
    title="Fleet Intelligence API",
    version="1.0.0"
)
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fleet-intelligence-demo-secret-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

DEMO_USERNAME = os.getenv("DEMO_USERNAME", "fleet_manager")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "fleet_demo_2026")
DEMO_ROLE = os.getenv("DEMO_ROLE", "fleet_manager")

SEARCH_RATE_LIMIT = 10
SEARCH_RATE_WINDOW_SECONDS = 60
search_rate_limits = {}


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "fleet_db"),
    "user": os.getenv("DB_USER", "fleet_user"),
    "password": os.getenv("DB_PASSWORD", "fleet_password"),
}




def calculate_average_temperature_by_oem():
    """
    Calculate average engine temperature for each OEM.
    """
    conn = get_db()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    v.oem,
                    ROUND(AVG(t.engine_temp)::numeric, 2) AS average_engine_temp
                FROM vehicle_telemetry t
                JOIN vehicle v ON v.vehicle_id = t.vehicle_id
                GROUP BY v.oem
                ORDER BY average_engine_temp DESC
            """)
            return cur.fetchall()

    finally:
        conn.close()

def calculate_incident_batch_analytics():
    """
    Batch analytics:
      - incident count by type
      - incident count by OEM
      - incident count by hour
    """
    conn = get_db()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    i.incident_type,
                    COUNT(*) AS incident_count
                FROM incident i
                GROUP BY i.incident_type
                ORDER BY incident_count DESC
            """)
            by_type = cur.fetchall()

            cur.execute("""
                SELECT
                    v.oem,
                    COUNT(*) AS incident_count
                FROM incident i
                JOIN vehicle v ON v.vehicle_id = i.vehicle_id
                GROUP BY v.oem
                ORDER BY incident_count DESC
            """)
            by_oem = cur.fetchall()

            cur.execute("""
                SELECT
                    EXTRACT(HOUR FROM i.event_timestamp)::int AS hour,
                    COUNT(*) AS incident_count
                FROM incident i
                GROUP BY hour
                ORDER BY hour
            """)
            by_hour = cur.fetchall()

        return {
            "by_type": by_type,
            "by_oem": by_oem,
            "by_hour": by_hour,
        }

    finally:
        conn.close()

def calculate_top_k_problematic_vehicles(k=5):
    """
    Find the top-K problematic vehicles using a min-heap.

    Problem score:
      CRITICAL = 3 points
      HIGH     = 2 points
      MEDIUM   = 1 point

    Complexity: O(n log k)
    """
    conn = get_db()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    v.vehicle_id,
                    v.vin,
                    v.oem,
                    v.health_score,
                    COUNT(i.incident_id) AS incident_count,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN i.severity = 'CRITICAL' THEN 3
                                WHEN i.severity = 'HIGH' THEN 2
                                WHEN i.severity = 'MEDIUM' THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS problem_score
                FROM vehicle v
                LEFT JOIN incident i
                    ON v.vehicle_id = i.vehicle_id
                GROUP BY
                    v.vehicle_id,
                    v.vin,
                    v.oem,
                    v.health_score
                """
            )
            vehicles = cur.fetchall()

        heap = []

        for vehicle in vehicles:
            score = int(vehicle["problem_score"])
            incident_count = int(vehicle["incident_count"])
            health_score = float(vehicle["health_score"])

            # Add only comparable values to the heap.
            # Store the vehicle row separately.
            key = (
                score,
                incident_count,
                -health_score,
                int(vehicle["vehicle_id"]),
            )

            if len(heap) < k:
                heapq.heappush(heap, (key, vehicle))
            elif key > heap[0][0]:
                heapq.heapreplace(heap, (key, vehicle))

        top_k = [
            item[1]
            for item in sorted(
                heap,
                key=lambda x: x[0],
                reverse=True,
            )
        ]

        return top_k

    finally:
        conn.close()

def calculate_incident_escalation(window_minutes=60):
    """
    Sliding-window incident analysis.

    For each vehicle, maintain a rolling time window and count
    incidents occurring within the last `window_minutes`.

    Escalation:
      0-1 incidents -> NORMAL
      2 incidents   -> ELEVATED
      3+ incidents   -> ESCALATED
    """
    conn = get_db()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    i.incident_id,
                    i.vehicle_id,
                    v.vin,
                    i.incident_type,
                    i.severity,
                    i.event_timestamp
                FROM incident i
                JOIN vehicle v ON v.vehicle_id = i.vehicle_id
                ORDER BY i.vehicle_id, i.event_timestamp
                """
            )

            incidents = cur.fetchall()

        windows = {}
        results = []

        for incident in incidents:
            vehicle_id = incident["vehicle_id"]
            event_time = incident["event_timestamp"]

            if vehicle_id not in windows:
                windows[vehicle_id] = []

            window = windows[vehicle_id]

            cutoff = event_time - timedelta(minutes=window_minutes)

            while window and window[0]["event_timestamp"] < cutoff:
                window.pop(0)

            window.append(incident)

            incident_count = len(window)

            if incident_count >= 3:
                escalation = "ESCALATED"
            elif incident_count == 2:
                escalation = "ELEVATED"
            else:
                escalation = "NORMAL"

            results.append({
                "vehicle_id": vehicle_id,
                "vehicle_code": incident["vin"],
                "incident_id": incident["incident_id"],
                "incident_type": incident["incident_type"],
                "severity": incident["severity"],
                "event_timestamp": event_time,
                "rolling_incident_count": incident_count,
                "escalation": escalation,
            })

        return results

    finally:
        conn.close()


def get_db():
    return psycopg2.connect(**DB_CONFIG)


security = HTTPBearer()


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    username = payload.get("sub")
    role = payload.get("role")

    if not username or not role:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
        )

    if role != DEMO_ROLE:
        raise HTTPException(
            status_code=403,
            detail="Fleet manager role required",
        )

    return {
        "username": username,
        "role": role,
    }


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(request: LoginRequest):

    if (
        request.username != DEMO_USERNAME
        or request.password != DEMO_PASSWORD
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": DEMO_USERNAME,
        "role": DEMO_ROLE,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": DEMO_ROLE,
    }


@app.get("/")
def root():
    return {
        "service": "Fleet Intelligence API",
        "status": "running"
    }


@app.get("/api/dashboard")
def dashboard():

    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            COUNT(*) AS total_vehicles,
            COUNT(*) FILTER (
                WHERE health_score > 0
            ) AS active_vehicles,
            COALESCE(AVG(health_score), 0) AS average_health_score
        FROM vehicle
    """)

    fleet = cursor.fetchone()

    cursor.execute("""
        SELECT
            COALESCE(AVG(battery_pct), 0) AS average_battery,
            COALESCE(AVG(engine_temp), 0) AS average_temperature
        FROM vehicle_telemetry
    """)

    telemetry = cursor.fetchone()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_incidents,
            COUNT(*) FILTER (
                WHERE severity = 'CRITICAL'
            ) AS critical_incidents
        FROM incident
    """)

    incidents = cursor.fetchone()

    cursor.close()
    db.close()

    return {
        "total_vehicles": fleet["total_vehicles"],
        "active_vehicles": fleet["active_vehicles"],
        "average_health_score": round(
            float(fleet["average_health_score"]), 2
        ),
        "average_battery": round(
            float(telemetry["average_battery"]), 2
        ),
        "average_temperature": round(
            float(telemetry["average_temperature"]), 2
        ),
        "total_incidents": incidents["total_incidents"],
        "critical_incidents": incidents["critical_incidents"]
    }


@app.get("/api/vehicles")
def vehicles():

    db = get_db()
    cursor = db.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            vehicle_id,
            vin,
            oem,
            model,
            health_score,
            created_at
        FROM vehicle
        ORDER BY vehicle_id
    """)

    rows = cursor.fetchall()

    cursor.close()
    db.close()

    return {
        "count": len(rows),
        "vehicles": rows
    }


@app.get("/api/analytics/escalation")
def incident_escalation(
    window_minutes: int = 60,
    user=Depends(require_auth),
):
    if window_minutes < 1 or window_minutes > 1440:
        raise HTTPException(
            status_code=400,
            detail="window_minutes must be between 1 and 1440",
        )

    results = calculate_incident_escalation(window_minutes)

    return {
        "window_minutes": window_minutes,
        "count": len(results),
        "results": results,
    }


@app.get("/api/vehicles/critical")
def critical_vehicles(user=Depends(require_auth)):

    db = get_db()
    cursor = db.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            v.vehicle_id,
            v.vin,
            v.oem,
            v.model,
            v.health_score,
            COUNT(i.incident_id) AS critical_incidents
        FROM vehicle v
        LEFT JOIN incident i
            ON v.vehicle_id = i.vehicle_id
            AND i.severity = 'CRITICAL'
        WHERE v.health_score < 60
           OR EXISTS (
                SELECT 1
                FROM incident ci
                WHERE ci.vehicle_id = v.vehicle_id
                  AND ci.severity = 'CRITICAL'
           )
        GROUP BY
            v.vehicle_id,
            v.vin,
            v.oem,
            v.model,
            v.health_score
        ORDER BY
            v.health_score ASC,
            critical_incidents DESC,
            v.vehicle_id ASC
        LIMIT 10
    """)

    rows = cursor.fetchall()

    cursor.close()
    db.close()

    return {
        "count": len(rows),
        "vehicles": rows
    }


@app.get("/api/vehicles/{vehicle_id}")
def vehicle_details(vehicle_id: int):

    db = get_db()
    cursor = db.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            vehicle_id,
            vin,
            oem,
            model,
            health_score,
            created_at
        FROM vehicle
        WHERE vehicle_id = %s
    """, (vehicle_id,))

    vehicle = cursor.fetchone()

    if not vehicle:
        cursor.close()
        db.close()
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    cursor.execute("""
        SELECT
            event_timestamp,
            latitude,
            longitude,
            speed_kmh,
            engine_temp,
            battery_pct
        FROM vehicle_telemetry
        WHERE vehicle_id = %s
        ORDER BY event_timestamp DESC
        LIMIT 20
    """, (vehicle_id,))

    telemetry = cursor.fetchall()

    cursor.execute("""
        SELECT
            incident_id,
            incident_type,
            severity,
            description,
            event_timestamp,
            latitude,
            longitude
        FROM incident
        WHERE vehicle_id = %s
        ORDER BY event_timestamp DESC
        LIMIT 20
    """, (vehicle_id,))

    incidents = cursor.fetchall()

    cursor.close()
    db.close()

    return {
        "vehicle": vehicle,
        "recent_telemetry": telemetry,
        "recent_incidents": incidents
    }


@app.get("/api/incidents")
def incidents():

    db = get_db()
    cursor = db.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            i.incident_id,
            v.vin,
            i.incident_type,
            i.severity,
            i.description,
            i.event_timestamp,
            i.latitude,
            i.longitude
        FROM incident i
        JOIN vehicle v
            ON i.vehicle_id = v.vehicle_id
        ORDER BY i.event_timestamp DESC
        LIMIT 100
    """)

    rows = cursor.fetchall()

    cursor.close()
    db.close()

    return {
        "count": len(rows),
        "incidents": rows
    }



@app.get("/api/analytics/incidents")
def incident_analytics():

    db = get_db()
    cursor = db.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            incident_type,
            severity,
            COUNT(*) AS count
        FROM incident
        GROUP BY incident_type, severity
        ORDER BY count DESC
    """)

    rows = cursor.fetchall()

    cursor.close()
    db.close()

    return {
        "count": len(rows),
        "breakdown": rows
    }


# ---------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    k: int = 10


@app.post("/api/search")
def semantic_search(request: SearchRequest, user=Depends(require_auth)):

    now = time.time()
    username = user["username"]

    user_limit = search_rate_limits.get(
        username,
        {"window_start": now, "count": 0},
    )

    if now - user_limit["window_start"] >= SEARCH_RATE_WINDOW_SECONDS:
        user_limit = {
            "window_start": now,
            "count": 0,
        }

    if user_limit["count"] >= SEARCH_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Search rate limit exceeded. Try again later.",
        )

    user_limit["count"] += 1
    search_rate_limits[username] = user_limit

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    if request.k < 1 or request.k > 50:
        raise HTTPException(
            status_code=400,
            detail="k must be between 1 and 50"
        )

    try:
        results = search(
            request.query,
            request.k
        )

        return {
            "query": request.query,
            "count": len(results),
            "results": results
        }

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.get("/api/analytics/top-vehicles")
def top_problematic_vehicles(
    k: int = 5,
    user=Depends(require_auth),
):
    if k < 1 or k > 50:
        raise HTTPException(
            status_code=400,
            detail="k must be between 1 and 50",
        )

    vehicles = calculate_top_k_problematic_vehicles(k)

    return {
        "k": k,
        "count": len(vehicles),
        "vehicles": vehicles,
    }


@app.get("/api/analytics/batch")
def batch_analytics(user=Depends(require_auth)):
    analytics = calculate_incident_batch_analytics()
    analytics["average_temperature_by_oem"] = calculate_average_temperature_by_oem()
    return analytics
