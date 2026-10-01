import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Battery,
  Car,
  Gauge,
  Thermometer,
  RefreshCw,
  ShieldAlert,
  Search,
} from "lucide-react";
import "./App.css";

const API = "http://localhost:8000";

async function getAuthToken() {
  const response = await fetch(`${API}/api/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
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

function StatCard({ title, value, icon: Icon, suffix = "" }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">
        <Icon size={22} />
      </div>

      <div>
        <p>{title}</p>
        <h2>
          {value}
          {suffix}
        </h2>
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
  const [error, setError] = useState("");

  const fetchData = async () => {
    try {
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
          fetch(`${API}/api/analytics/incidents`),
        ]);

      if (!dashboardRes.ok || !criticalRes.ok || !analyticsRes.ok) {
        throw new Error("API request failed");
      }

      const dashboardData = await dashboardRes.json();
      const criticalData = await criticalRes.json();
      const analyticsData = await analyticsRes.json();

      setDashboard(dashboardData);
      setCritical(criticalData.vehicles || []);
      setAnalytics(analyticsData.breakdown || []);
    } catch (err) {
      console.error(err);
      setError(
        err.message || "Unable to connect to Fleet Intelligence API."
      );
    } finally {
      setLoading(false);
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
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Search request failed");
      }

      const data = await response.json();
      setSearchResults(data.results || []);
    } catch (err) {
      console.error(err);
      setSearchResults([]);
      setSearchError(err.message || "Unable to perform semantic search.");
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
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Unable to load vehicle details");
      }

      const data = await response.json();
      setSelectedVehicle(data);
    } catch (err) {
      console.error(err);
      setVehicleError(err.message || "Unable to load vehicle details.");
    } finally {
      setVehicleLoading(false);
    }
  };

  const closeVehicleDetail = () => {
    setSelectedVehicle(null);
    setVehicleError("");
  };

  useEffect(() => {
    fetchData();

    const interval = setInterval(fetchData, 10000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="loading-screen">
        <Activity size={38} />
        <h2>Fleet Intelligence</h2>
        <p>Connecting to telemetry backend...</p>
      </div>
    );
  }

  return (
    <div className="app">

      <header className="topbar">

        <div className="brand">
          <div className="brand-icon">
            <Activity size={24} />
          </div>

          <div>
            <h1>Fleet Intelligence</h1>
            <p>Real-time fleet telemetry & health monitoring</p>
          </div>
        </div>

        <div className="topbar-right">

          <div className="live-status">
            <span className="live-dot"></span>
            LIVE
          </div>

          <button className="refresh-btn" onClick={fetchData}>
            <RefreshCw size={17} />
            Refresh
          </button>

        </div>

      </header>

      <main className="dashboard">

        {error && (
          <div className="error-banner">
            <AlertTriangle size={18} />
            {error}
          </div>
        )}

        <section className="section-header">

          <div>
            <h2>Fleet Overview</h2>
            <p>
              Current operational health across the connected fleet
            </p>
          </div>

        </section>

        <section className="stats-grid">

          <StatCard
            title="Total Vehicles"
            value={dashboard?.total_vehicles ?? 0}
            icon={Car}
          />

          <StatCard
            title="Active Vehicles"
            value={dashboard?.active_vehicles ?? 0}
            icon={Activity}
          />

          <StatCard
            title="Average Health"
            value={dashboard?.average_health_score ?? 0}
            suffix="%"
            icon={Gauge}
          />

          <StatCard
            title="Average Battery"
            value={dashboard?.average_battery ?? 0}
            suffix="%"
            icon={Battery}
          />

          <StatCard
            title="Avg Temperature"
            value={dashboard?.average_temperature ?? 0}
            suffix="°C"
            icon={Thermometer}
          />

          <StatCard
            title="Critical Incidents"
            value={dashboard?.critical_incidents ?? 0}
            icon={ShieldAlert}
          />

        </section>

        <section className="panel search-panel">

          <div className="panel-header">

            <div>
              <h2>Semantic Incident Search</h2>
              <p>Search fleet incidents using natural language</p>
            </div>

            <Search size={22} />

          </div>

          <div className="search-box">

            <input
              className="search-input"
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  performSearch();
                }
              }}
              placeholder="Try: vehicles overheating while stopped"
            />

            <button
              className="search-btn"
              onClick={performSearch}
              disabled={searchLoading}
            >
              <Search size={17} />
              {searchLoading ? "Searching..." : "Search"}
            </button>

          </div>

          {searchError && (
            <div className="search-error">
              {searchError}
            </div>
          )}

          {searchResults.length > 0 ? (

            <div className="search-results">

              <table>

                <thead>

                  <tr>
                    <th>Vehicle</th>
                    <th>Incident</th>
                    <th>Severity</th>
                    <th>Timestamp</th>
                    <th>Distance</th>
                  </tr>

                </thead>

                <tbody>

                  {searchResults.map((result) => (

                    <tr
                      key={result.incident_id}
                      onClick={() => openVehicleDetail(result.vehicle_id)}
                    >

                      <td>
                        <span className="search-vehicle">
                          {result.vehicle_code}
                        </span>
                      </td>

                      <td>
                        {result.incident_type}
                      </td>

                      <td>
                        <span
                          className={`search-severity ${String(
                            result.severity
                          ).toLowerCase()}`}
                        >
                          {result.severity}
                        </span>
                      </td>

                      <td>
                        {result.event_timestamp
                          ? new Date(
                              result.event_timestamp
                            ).toLocaleString()
                          : "—"}
                      </td>

                      <td>
                        <span className="search-distance">
                          {Number(result.distance).toFixed(4)}
                        </span>
                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          ) : (

            !searchLoading &&
            searchQuery &&
            !searchError && (
              <div className="search-empty">
                No matching incidents found.
              </div>
            )

          )}

        </section>

        {vehicleLoading && (
          <section className="panel vehicle-detail-panel">
            <div className="vehicle-detail-loading">
              <Activity size={22} />
              Loading vehicle details...
            </div>
          </section>
        )}

        {vehicleError && (
          <section className="panel vehicle-detail-panel">
            <div className="search-error">
              {vehicleError}
            </div>
          </section>
        )}

        {selectedVehicle && !vehicleLoading && (
          <section className="panel vehicle-detail-panel">

            <div className="panel-header">

              <div>
                <h2>
                  Vehicle Details — {selectedVehicle.vehicle?.vin}
                </h2>
                <p>
                  Detailed telemetry and incident information
                </p>
              </div>

              <button
                className="refresh-btn"
                onClick={closeVehicleDetail}
              >
                Close
              </button>

            </div>

            <div className="vehicle-detail-grid">

              <div className="vehicle-detail-card">
                <span>Vehicle</span>
                <strong>
                  {selectedVehicle.vehicle?.vin || "—"}
                </strong>
              </div>

              <div className="vehicle-detail-card">
                <span>OEM</span>
                <strong>
                  {selectedVehicle.vehicle?.oem || "—"}
                </strong>
              </div>

              <div className="vehicle-detail-card">
                <span>Model</span>
                <strong>
                  {selectedVehicle.vehicle?.model || "—"}
                </strong>
              </div>

              <div className="vehicle-detail-card">
                <span>Health Score</span>
                <strong>
                  {selectedVehicle.vehicle?.health_score ?? "—"}%
                </strong>
              </div>

            </div>

            <div className="vehicle-detail-content">

              <div>

                <h3>Latest Telemetry</h3>

                {selectedVehicle.recent_telemetry?.length > 0 ? (

                  <div className="table-wrapper">

                    <table>

                      <thead>
                        <tr>
                          <th>Timestamp</th>
                          <th>Speed</th>
                          <th>Temperature</th>
                          <th>Battery</th>
                          <th>Location</th>
                        </tr>
                      </thead>

                      <tbody>

                        {selectedVehicle.recent_telemetry.map(
                          (telemetry, index) => (

                            <tr key={index}>

                              <td>
                                {new Date(
                                  telemetry.event_timestamp
                                ).toLocaleString()}
                              </td>

                              <td>
                                {telemetry.speed_kmh} km/h
                              </td>

                              <td>
                                {telemetry.engine_temp} °C
                              </td>

                              <td>
                                {telemetry.battery_pct}%
                              </td>

                              <td>
                                {Number(telemetry.latitude).toFixed(4)},
                                {" "}
                                {Number(telemetry.longitude).toFixed(4)}
                              </td>

                            </tr>

                          )
                        )}

                      </tbody>

                    </table>

                  </div>

                ) : (
                  <p className="search-empty">
                    No recent telemetry available.
                  </p>
                )}

              </div>

              <div>

                <h3>Recent Incidents</h3>

                {selectedVehicle.recent_incidents?.length > 0 ? (

                  <div className="incident-list">

                    {selectedVehicle.recent_incidents.map(
                      (incident) => (

                        <div
                          className="incident-row"
                          key={incident.incident_id}
                        >

                          <div className="incident-info">

                            <span
                              className={`severity-dot ${String(
                                incident.severity
                              ).toLowerCase()}`}
                            ></span>

                            <div>
                              <strong>
                                {incident.incident_type}
                              </strong>

                              <span>
                                {incident.description || "Incident detected"}
                              </span>
                            </div>

                          </div>

                        </div>

                      )
                    )}

                  </div>

                ) : (
                  <p className="search-empty">
                    No recent incidents.
                  </p>
                )}

              </div>

            </div>

          </section>
        )}

        <section className="content-grid">

          <div className="panel">

            <div className="panel-header">

              <div>
                <h2>Incident Analytics</h2>
                <p>Detected incidents by type and severity</p>
              </div>

              <AlertTriangle size={22} />

            </div>

            <div className="incident-list">

              {analytics.map((item, index) => (

                <div className="incident-row" key={index}>

                  <div className="incident-info">

                    <div
                      className={`severity-dot ${String(
                        item.severity
                      ).toLowerCase()}`}
                    ></div>

                    <div>
                      <strong>
                        {String(item.incident_type).replaceAll(
                          "_",
                          " "
                        )}
                      </strong>

                      <span>{item.severity}</span>
                    </div>

                  </div>

                  <div className="incident-count">
                    {item.count}
                  </div>

                </div>

              ))}

            </div>

          </div>

          <div className="panel">

            <div className="panel-header">

              <div>
                <h2>Fleet Health</h2>
                <p>Current fleet health score</p>
              </div>

              <Gauge size={22} />

            </div>

            <div className="health-summary">

              <div className="health-score">
                <span>
                  {dashboard?.average_health_score ?? 0}
                </span>

                <small>Average Score</small>
              </div>

              <div className="health-bar-container">

                <div
                  className="health-bar"
                  style={{
                    width: `${dashboard?.average_health_score ?? 0}%`,
                  }}
                ></div>

              </div>

              <p className="health-description">
                Health score is calculated from battery level,
                engine temperature and critical operating conditions.
              </p>

            </div>

          </div>

        </section>

        <section className="panel critical-panel">

          <div className="panel-header">

            <div>
              <h2>Critical & At-Risk Vehicles</h2>
              <p>
                Vehicles requiring attention based on health or
                critical incidents
              </p>
            </div>

            <div className="critical-count">
              {critical.length} vehicles
            </div>

          </div>

          <div className="table-wrapper">

            <table>

              <thead>

                <tr>
                  <th>Vehicle</th>
                  <th>OEM</th>
                  <th>Health Score</th>
                  <th>Critical Incidents</th>
                  <th>Status</th>
                </tr>

              </thead>

              <tbody>

                {critical.map((vehicle) => {

                  const health = Number(vehicle.health_score);

                  const status =
                    health < 30 ? "Critical" : "At Risk";

                  return (

                    <tr key={vehicle.vehicle_id}>

                      <td>
                        <div className="vehicle-cell">
                          <Car size={18} />
                          <strong>{vehicle.vin}</strong>
                        </div>
                      </td>

                      <td>{vehicle.oem}</td>

                      <td>

                        <div className="health-cell">

                          <div className="mini-bar">
                            <div
                              style={{
                                width: `${health}%`,
                              }}
                            ></div>
                          </div>

                          <span>{health}%</span>

                        </div>

                      </td>

                      <td>
                        <span className="incident-badge">
                          {vehicle.critical_incidents}
                        </span>
                      </td>

                      <td>

                        <span
                          className={`status-badge ${
                            status === "Critical"
                              ? "critical"
                              : "risk"
                          }`}
                        >
                          {status}
                        </span>

                      </td>

                    </tr>

                  );

                })}

              </tbody>

            </table>

          </div>

        </section>

      </main>

      <footer>
        Fleet Intelligence • Redis → Processor → PostgreSQL → FastAPI
      </footer>

    </div>
  );
}

export default App;
