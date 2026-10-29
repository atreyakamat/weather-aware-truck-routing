import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { postPlan } from "./lib/api.js";
import { RISK } from "./lib/risk.js";
import PlanForm from "./components/PlanForm.jsx";
import MapView from "./components/MapView.jsx";
import RouteCards from "./components/RouteCards.jsx";
import TimeSlider from "./components/TimeSlider.jsx";

export default function App() {
  const [selectedRouteId, setSelectedRouteId] = useState(0);
  const [hour, setHour] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showHeat, setShowHeat] = useState(false);

  const mutation = useMutation({
    mutationFn: postPlan,
    onSuccess: (data) => {
      setSelectedRouteId(data.recommended_id);
      setHour(0);
      setPlaying(false);
    },
  });

  const result = mutation.data;

  useEffect(() => {
    if (!showHeat) setPlaying(false);
  }, [showHeat]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Weather-Aware Truck Routing</h1>
        <p>Safest route by weather, load weight &amp; travel time.</p>
      </header>

      <aside className="sidebar">
        <PlanForm onSubmit={mutation.mutate} loading={mutation.isPending} />
        {mutation.isError && <div className="error">⚠ {mutation.error.message}</div>}
        {result?.demo_mode && (
          <div className="demo-note">
            Demo mode: synthetic routes (no HERE key set). Weather &amp; risk are real.
          </div>
        )}
        {result && (
          <RouteCards
            result={result}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
          />
        )}
        <Legend />
      </aside>

      <main className="content">
        {result ? (
          <>
            <div className="map-toolbar">
              <label className="toggle">
                <input type="checkbox" checked={showHeat} onChange={(e) => setShowHeat(e.target.checked)} />
                Weather heatmap
              </label>
              {showHeat && (
                <TimeSlider
                  hours={result.corridor.hours}
                  hour={hour}
                  setHour={setHour}
                  playing={playing}
                  setPlaying={setPlaying}
                />
              )}
            </div>
            <MapView
              result={result}
              selectedRouteId={selectedRouteId}
              onSelectRoute={setSelectedRouteId}
              showHeat={showHeat}
              hour={hour}
            />
          </>
        ) : (
          <div className="placeholder">
            {mutation.isPending ? "Planning your route…" : "Enter a trip to see routes, risk and weather."}
          </div>
        )}
      </main>
    </div>
  );
}

function Legend() {
  return (
    <div className="legend">
      <span className="legend-title">Risk</span>
      {RISK.map((r, i) => (
        <span key={i} className="legend-item">
          <span className="swatch" style={{ background: r.color }} />
          {r.label}
        </span>
      ))}
    </div>
  );
}
