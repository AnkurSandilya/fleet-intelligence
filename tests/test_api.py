from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from api.main import (
    calculate_top_k_problematic_vehicles,
    calculate_incident_escalation,
)


def mock_db(rows):
    """
    Create a fake DB connection whose cursor returns the supplied rows.
    """
    conn = MagicMock()
    cursor = MagicMock()

    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = None
    cursor.fetchall.return_value = rows

    conn.cursor.return_value = cursor
    return conn


def test_top_k_problematic_vehicles():
    rows = [
        {
            "vehicle_id": 1,
            "vin": "VH001",
            "oem": "OEM_A",
            "health_score": 80,
            "incident_count": 2,
            "problem_score": 5,  # 1 CRITICAL + 1 HIGH
        },
        {
            "vehicle_id": 2,
            "vin": "VH002",
            "oem": "OEM_B",
            "health_score": 60,
            "incident_count": 3,
            "problem_score": 7,  # 2 CRITICAL + 1 MEDIUM
        },
        {
            "vehicle_id": 3,
            "vin": "VH003",
            "oem": "OEM_A",
            "health_score": 90,
            "incident_count": 1,
            "problem_score": 3,
        },
    ]

    conn = mock_db(rows)

    with patch("api.main.get_db", return_value=conn):
        result = calculate_top_k_problematic_vehicles(k=2)

    assert len(result) == 2
    assert result[0]["vehicle_id"] == 2
    assert result[1]["vehicle_id"] == 1


def test_incident_escalation():
    base_time = datetime(2026, 9, 28, 10, 0, 0)

    rows = [
        {
            "incident_id": 1,
            "vehicle_id": 1,
            "vin": "VH001",
            "incident_type": "OVERHEATING",
            "severity": "HIGH",
            "event_timestamp": base_time,
        },
        {
            "incident_id": 2,
            "vehicle_id": 1,
            "vin": "VH001",
            "incident_type": "LOW_BATTERY",
            "severity": "MEDIUM",
            "event_timestamp": base_time + timedelta(minutes=10),
        },
        {
            "incident_id": 3,
            "vehicle_id": 1,
            "vin": "VH001",
            "incident_type": "OVERHEATING_STOP",
            "severity": "CRITICAL",
            "event_timestamp": base_time + timedelta(minutes=20),
        },
    ]

    conn = mock_db(rows)

    with patch("api.main.get_db", return_value=conn):
        result = calculate_incident_escalation(window_minutes=60)

    assert len(result) == 3
    assert result[0]["escalation"] == "NORMAL"
    assert result[1]["escalation"] == "ELEVATED"
    assert result[2]["escalation"] == "ESCALATED"


def test_incident_escalation_window_expires():
    base_time = datetime(2026, 9, 28, 10, 0, 0)

    rows = [
        {
            "incident_id": 1,
            "vehicle_id": 1,
            "vin": "VH001",
            "incident_type": "OVERHEATING",
            "severity": "HIGH",
            "event_timestamp": base_time,
        },
        {
            "incident_id": 2,
            "vehicle_id": 1,
            "vin": "VH001",
            "incident_type": "LOW_BATTERY",
            "severity": "MEDIUM",
            "event_timestamp": base_time + timedelta(minutes=10),
        },
        {
            "incident_id": 3,
            "vehicle_id": 1,
            "vin": "VH001",
            "incident_type": "OVERHEATING",
            "severity": "HIGH",
            "event_timestamp": base_time + timedelta(minutes=70),
        },
    ]

    conn = mock_db(rows)

    with patch("api.main.get_db", return_value=conn):
        result = calculate_incident_escalation(window_minutes=60)

    assert result[0]["rolling_incident_count"] == 1
    assert result[1]["rolling_incident_count"] == 2
    assert result[2]["rolling_incident_count"] == 2
    assert result[2]["escalation"] == "ELEVATED"
