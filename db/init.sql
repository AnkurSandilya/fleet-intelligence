-- ============================================
-- Fleet Telemetry Intelligence Platform
-- PostgreSQL Schema
-- ============================================

CREATE TABLE IF NOT EXISTS fleet (
    fleet_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS driver (
    driver_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicle (
    vehicle_id SERIAL PRIMARY KEY,
    vin VARCHAR(17) UNIQUE NOT NULL,
    fleet_id INTEGER REFERENCES fleet(fleet_id),
    driver_id INTEGER REFERENCES driver(driver_id),
    oem VARCHAR(50) NOT NULL,
    model VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscription (
    subscription_id SERIAL PRIMARY KEY,
    fleet_id INTEGER REFERENCES fleet(fleet_id),
    plan_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicle_telemetry (
    telemetry_id BIGSERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicle(vehicle_id),
    event_id VARCHAR(100) UNIQUE NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    speed_kmh DOUBLE PRECISION,
    engine_temp DOUBLE PRECISION,
    battery_pct DOUBLE PRECISION,
    dtc TEXT[],
    event_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incident (
    incident_id BIGSERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicle(vehicle_id),
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT,
    event_timestamp TIMESTAMP NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    embedding_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries

CREATE INDEX IF NOT EXISTS idx_vehicle_vin
ON vehicle(vin);

CREATE INDEX IF NOT EXISTS idx_telemetry_vehicle_time
ON vehicle_telemetry(vehicle_id, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_incident_vehicle_time
ON incident(vehicle_id, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_incident_type
ON incident(incident_type);

CREATE INDEX IF NOT EXISTS idx_incident_time
ON incident(event_timestamp DESC);
