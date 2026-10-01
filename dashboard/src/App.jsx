import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Battery,
  Car,
  CheckCircle2,
  ChevronRight,
  Gauge,
  MapPin,
  RefreshCw,
  Search,
  ShieldAlert,
  Thermometer,
  X,
} from "lucide-react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function getAuthToken() {
  const response = await fetch(`${API}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: "fleet_manager",
      password: "fleet_demo_2026",
    }),
  });

  if (!response.ok) {
    throw new Error("Dashboard authentication failed");
  }

  const data = await response.json();
  return data.access_token;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function severityClass(value) {
  return String(value || "").toLowerCase();
}

function Stat({ icon: Icon, label, value, suffix, tone = "" }) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">
        <Icon size={17} />
      </div>

      <div className="metric-content">
        <span>{label}</span>
        <strong>
          {value}
          {suffix && <small>{suffix}</small>}
        </strong>
      </div>
    </div>
  );
}

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [critical, setCritical] = useState([]);
  const [analytics, setAnalytics] = useState([]);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");

  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [vehicleLoading, setVehicleLoading] = useState(false);
  const [vehicleError, setVehicleError] = useState("");

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const fetchData = async (manual = false) => {
    try {
      if (manual) setRefreshing(true);
      setError("");

      const token = await getAuthToken();

      const [dashboardRes, criticalRes, analyticsRes] =
        await Promise.all([
          fetch(`${API}/api/dashboard`),
          fetch(`${API}/api/vehicles/critical`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }),
          fetch(`${API}/api/analytics/batch`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }),
        ]);

      if (!dashboardRes.ok || !criticalRes.ok || !analyticsRes.ok) {
        throw new Error("Unable to load fleet data");
      }

      const dashboardData = await dashboardRes.json();
      const criticalData = await criticalRes.json();
      const analyticsData = await analyticsRes.json();

      setDashboard(dashboardData);
      setCritical(criticalData.vehicles || []);
      setAnalytics(analyticsData.by_type || []);
      setLastUpdated(new Date());
    } catch (err) {
      console.error(err);
      setError(err.message || "Unable to connect to Fleet Intelligence API.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const performSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setSearchError("Enter a search query.");
      return;
    }

    try {
      setSearchLoading(true);
      setSearchError("");

      const token = await getAuthToken();

      const response = await fetch(`${API}/api/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query: searchQuery,
          k: 10,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Search request failed");
      }

      const data = await response.json();
      setSearchResults(data.results || []);
    } catch (err) {
      setSearchResults([]);
      setSearchError(err.message || "Unable to perform search.");
    } finally {
      setSearchLoading(false);
    }
  };

  const openVehicleDetail = async (vehicleId) => {
    try {
      setVehicleLoading(true);
      setVehicleError("");

      const response = await fetch(`${API}/api/vehicles/${vehicleId}`);

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Unable to load vehicle");
      }

      const data = await response.json();
      setSelectedVehicle(data);
    } catch (err) {
      setVehicleError(err.message || "Unable to load vehicle details.");
    } finally {
      setVehicleLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    const interval = setInterval(() => {
      fetchData();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const incidentTotal = useMemo(
    () =>
      analytics.reduce(
        (sum, item) => sum + Number(item.incident_count || 0),
        0
      ),
    [analytics]
  );

  const highestIncident = useMemo(() => {
    if (!analytics.length) return null;

    return [...analytics].sort(
      (a, b) =>
        Number(b.incident_count || 0) -
        Number(a.incident_count || 0)
    )[0];
  }, [analytics]);

  const health = Number(dashboard?.average_health_score || 0);

  const healthLabel =
    health >= 80 ? "Healthy" : health >= 60 ? "Moderate" : "Needs attention";

  const healthClass =
    health >= 80 ? "healthy" : health >= 60 ? "moderate" : "critical";

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-mark">
          <Activity size={24} />
        </div>
        <h2>Fleet Intelligence</h2>
        <p>Connecting to telemetry services...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <div className="brand-mark">
              <Activity size={19} />
            </div>

            <div>
              <div className="brand-name">Fleet Intelligence</div>
              <div className="brand-subtitle">
                Real-time fleet operations
              </div>
            </div>
          </div>

          <div className="system-status">
            <div className="service-status">
              <span className="status-dot green" />
              API
            </div>

            <div className="service-status">
              <span className="status-dot green" />
              Redis
            </div>

            <div className="service-status">
              <span className="status-dot green" />
              PostgreSQL
            </div>

            <div className="live-pill">
              <span />
              LIVE
            </div>

            <button
              className="icon-button"
              onClick={() => fetchData(true)}
              title="Refresh"
            >
              <RefreshCw
                size={16}
                className={refreshing ? "spin" : ""}
              />
            </button>
          </div>
        </div>
      </header>

      <main className="main">
        {error && (
          <div className="error-banner">
            <AlertTriangle size={16} />
            {error}
          </div>
        )}

        <section className="hero">
          <div>
            <div className="eyebrow">FLEET OVERVIEW</div>
            <h1>Operations at a glance.</h1>
            <p>
              Monitor vehicle health, incidents and live telemetry across
              your connected fleet.
            </p>
          </div>

          <div className="updated">
            <span>Last updated</span>
            <strong>{lastUpdated.toLocaleTimeString()}</strong>
          </div>
        </section>

        <section className="metrics">
          <Stat
            icon={Car}
            label="Total vehicles"
            value={formatNumber(dashboard?.total_vehicles)}
          />

          <Stat
            icon={Activity}
            label="Active vehicles"
            value={formatNumber(dashboard?.active_vehicles)}
            tone="positive"
          />

          <Stat
            icon={Gauge}
            label="Fleet health"
            value={Number(dashboard?.average_health_score || 0).toFixed(2)}
            suffix="%"
            tone={healthClass}
          />

          <Stat
            icon={Battery}
            label="Average battery"
            value={Number(dashboard?.average_battery || 0).toFixed(2)}
            suffix="%"
          />

          <Stat
            icon={Thermometer}
            label="Avg temperature"
            value={Number(dashboard?.average_temperature || 0).toFixed(0)}
            suffix="°C"
          />

          <Stat
            icon={ShieldAlert}
            label="Critical incidents"
            value={formatNumber(dashboard?.critical_incidents)}
            tone="danger"
          />
        </section>

        <section className="main-grid">
          <div className="panel incidents-panel">
            <div className="panel-heading">
              <div>
                <span className="section-label">INCIDENTS</span>
                <h2>Incident overview</h2>
              </div>

              <div className="total-chip">
                {formatNumber(incidentTotal)} total
              </div>
            </div>

            <div className="incident-chart">
              {analytics.map((item) => {
                const count = Number(item.incident_count || 0);
                const percentage =
                  incidentTotal > 0
                    ? (count / incidentTotal) * 100
                    : 0;

                const type = String(item.incident_type || "");
                const isCritical = type === "OVERHEATING_STOP";

                return (
                  <div className="incident-item" key={type}>
                    <div className="incident-top">
                      <div className="incident-name">
                        <span
                          className={`severity-indicator ${
                            isCritical ? "red" : "orange"
                          }`}
                        />

                        <div>
                          <strong>
                            {type.replaceAll("_", " ")}
                          </strong>

                          <span>
                            {isCritical ? "Critical" : "Detected incident"}
                          </span>
                        </div>
                      </div>

                      <div className="incident-value">
                        <strong>{formatNumber(count)}</strong>
                        <span>{percentage.toFixed(1)}%</span>
                      </div>
                    </div>

                    <div className="progress-track">
                      <div
                        className={`progress-fill ${
                          isCritical ? "red-fill" : ""
                        }`}
                        style={{
                          width: `${Math.max(percentage, 2)}%`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            {highestIncident && (
              <div className="insight">
                <div className="insight-icon">
                  <ArrowUpRight size={15} />
                </div>

                <div>
                  <span>Most frequent incident</span>
                  <strong>
                    {String(highestIncident.incident_type).replaceAll(
                      "_",
                      " "
                    )}
                  </strong>
                </div>

                <div className="insight-number">
                  {formatNumber(highestIncident.incident_count)}
                </div>
              </div>
            )}
          </div>

          <div className="panel health-panel">
            <div className="panel-heading">
              <div>
                <span className="section-label">HEALTH</span>
                <h2>Fleet health</h2>
              </div>

              <div className={`health-status ${healthClass}`}>
                <span />
                {healthLabel}
              </div>
            </div>

            <div className="health-hero">
              <div className="health-ring">
                <div>
                  <strong>{health.toFixed(1)}</strong>
                  <span>score</span>
                </div>
              </div>
            </div>

            <div className="health-copy">
              <strong>Current operational health</strong>
              <p>
                Health score combines battery level, engine temperature
                and critical operating conditions.
              </p>
            </div>

            <div className="health-stats">
              <div>
                <span>Battery</span>
                <strong>
                  {Number(dashboard?.average_battery || 0).toFixed(1)}%
                </strong>
              </div>

              <div>
                <span>Temperature</span>
                <strong>
                  {Number(dashboard?.average_temperature || 0).toFixed(0)}
                  °C
                </strong>
              </div>

              <div>
                <span>Active</span>
                <strong>
                  {formatNumber(dashboard?.active_vehicles)}
                </strong>
              </div>
            </div>
          </div>
        </section>

        <section className="panel search-panel">
          <div className="search-header">
            <div>
              <span className="section-label">AI SEARCH</span>
              <h2>Find incidents naturally</h2>
              <p>
                Search telemetry and incidents using natural language.
              </p>
            </div>

            <Search size={20} />
          </div>

          <div className="search-command">
            <Search size={17} />

            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") performSearch();
              }}
              placeholder="e.g. vehicles overheating while stopped"
            />

            <button onClick={performSearch} disabled={searchLoading}>
              {searchLoading ? "Searching..." : "Search"}
            </button>
          </div>

          {searchError && (
            <div className="search-error">
              <AlertTriangle size={14} />
              {searchError}
            </div>
          )}

          {searchResults.length > 0 && (
            <div className="search-results">
              <div className="results-header">
                <span>Search results</span>
                <strong>{searchResults.length} matches</strong>
              </div>

              {searchResults.map((result) => (
                <button
                  className="result-row"
                  key={result.incident_id}
                  onClick={() => openVehicleDetail(result.vehicle_id)}
                >
                  <div className="result-vehicle">
                    <span className="vehicle-avatar">
                      <Car size={14} />
                    </span>

                    <div>
                      <strong>{result.vehicle_code}</strong>
                      <span>{result.incident_type}</span>
                    </div>
                  </div>

                  <span
                    className={`severity-pill ${severityClass(
                      result.severity
                    )}`}
                  >
                    {result.severity}
                  </span>

                  <span className="result-time">
                    {result.event_timestamp
                      ? new Date(
                          result.event_timestamp
                        ).toLocaleString()
                      : "—"}
                  </span>

                  <span className="result-distance">
                    {Number(result.distance).toFixed(3)}
                  </span>

                  <ChevronRight size={16} />
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="panel critical-panel">
          <div className="panel-heading">
            <div>
              <span className="section-label">ATTENTION REQUIRED</span>
              <h2>Critical vehicles</h2>
            </div>

            <div className="critical-summary">
              <ShieldAlert size={14} />
              {critical.length} vehicles
            </div>
          </div>

          <div className="vehicle-table">
            <div className="table-head">
              <span>Vehicle</span>
              <span>OEM</span>
              <span>Health</span>
              <span>Incidents</span>
              <span>Status</span>
              <span />
            </div>

            {critical.map((vehicle) => {
              const score = Number(vehicle.health_score || 0);

              return (
                <button
                  className="vehicle-row"
                  key={vehicle.vehicle_id}
                  onClick={() => openVehicleDetail(vehicle.vehicle_id)}
                >
                  <div className="vehicle-main">
                    <div className="vehicle-avatar">
                      <Car size={14} />
                    </div>

                    <div>
                      <strong>{vehicle.vin}</strong>
                      <span>Vehicle {vehicle.vehicle_id}</span>
                    </div>
                  </div>

                  <span className="oem">{vehicle.oem}</span>

                  <div className="health-cell">
                    <strong>{score}%</strong>
                    <div className="mini-progress">
                      <span style={{ width: `${score}%` }} />
                    </div>
                  </div>

                  <span className="incident-count">
                    {vehicle.critical_incidents}
                  </span>

                  <span className="critical-status">
                    <span />
                    Critical
                  </span>

                  <ChevronRight size={16} />
                </button>
              );
            })}
          </div>
        </section>
      </main>

      <footer>
        Fleet Intelligence <span>•</span> Redis → Processor → PostgreSQL → FastAPI
      </footer>

      {(selectedVehicle || vehicleLoading) && (
        <div className="drawer-overlay" onClick={() => setSelectedVehicle(null)}>
          <aside
            className="vehicle-drawer"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="drawer-header">
              <div>
                <span className="section-label">VEHICLE DETAILS</span>
                <h2>
                  {selectedVehicle?.vehicle?.vin || "Loading..."}
                </h2>
              </div>

              <button
                className="drawer-close"
                onClick={() => setSelectedVehicle(null)}
              >
                <X size={18} />
              </button>
            </div>

            {vehicleLoading ? (
              <div className="drawer-loading">
                <Activity size={22} />
                Loading telemetry...
              </div>
            ) : vehicleError ? (
              <div className="drawer-error">
                <AlertTriangle size={17} />
                {vehicleError}
              </div>
            ) : (
              <>
                <div className="drawer-health">
                  <div>
                    <span>Health score</span>
                    <strong>
                      {selectedVehicle?.vehicle?.health_score ?? "—"}%
                    </strong>
                  </div>

                  <div className="drawer-health-ring">
                    <CheckCircle2 size={20} />
                  </div>
                </div>

                <div className="drawer-grid">
                  <div>
                    <span>OEM</span>
                    <strong>
                      {selectedVehicle?.vehicle?.oem || "—"}
                    </strong>
                  </div>

                  <div>
                    <span>Model</span>
                    <strong>
                      {selectedVehicle?.vehicle?.model || "—"}
                    </strong>
                  </div>
                </div>

                <div className="drawer-section">
                  <div className="drawer-section-title">
                    <Activity size={15} />
                    Latest telemetry
                  </div>

                  {selectedVehicle?.recent_telemetry?.length > 0 ? (
                    selectedVehicle.recent_telemetry
                      .slice(0, 5)
                      .map((telemetry, index) => (
                        <div className="telemetry-row" key={index}>
                          <div>
                            <span>Speed</span>
                            <strong>
                              {telemetry.speed_kmh} km/h
                            </strong>
                          </div>

                          <div>
                            <span>Temperature</span>
                            <strong>
                              {telemetry.engine_temp}°C
                            </strong>
                          </div>

                          <div>
                            <span>Battery</span>
                            <strong>
                              {telemetry.battery_pct}%
                            </strong>
                          </div>
                        </div>
                      ))
                  ) : (
                    <p className="drawer-empty">
                      No telemetry available.
                    </p>
                  )}
                </div>

                <div className="drawer-section">
                  <div className="drawer-section-title">
                    <ShieldAlert size={15} />
                    Recent incidents
                  </div>

                  {selectedVehicle?.recent_incidents?.length > 0 ? (
                    selectedVehicle.recent_incidents
                      .slice(0, 6)
                      .map((incident) => (
                        <div
                          className="drawer-incident"
                          key={incident.incident_id}
                        >
                          <span
                            className={`severity-indicator ${severityClass(
                              incident.severity
                            )}`}
                          />

                          <div>
                            <strong>
                              {incident.incident_type}
                            </strong>

                            <span>
                              {incident.description ||
                                "Incident detected"}
                            </span>
                          </div>

                          <em>{incident.severity}</em>
                        </div>
                      ))
                  ) : (
                    <p className="drawer-empty">
                      No recent incidents.
                    </p>
                  )}
                </div>

                <div className="drawer-location">
                  <MapPin size={15} />
                  <span>Vehicle telemetry location available</span>
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

export default App;
