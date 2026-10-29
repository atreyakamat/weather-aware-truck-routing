import { riskColor, riskLabel } from "../lib/risk.js";

function hours(min) {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return `${h}h ${m}m`;
}

export default function RouteCards({ result, selectedRouteId, onSelectRoute }) {
  return (
    <div className="route-cards">
      {result.routes.map((r) => {
        const recommended = r.id === result.recommended_id;
        const active = r.id === selectedRouteId;
        return (
          <button
            key={r.id}
            className={`route-card${active ? " active" : ""}${recommended ? " recommended" : ""}`}
            onClick={() => onSelectRoute(r.id)}
          >
            <div className="route-card-head">
              <span className="route-name">{r.label}</span>
              {recommended && <span className="badge-rec">Recommended</span>}
              {r.has_no_travel && <span className="badge-notravel">No-Travel segment</span>}
            </div>
            <div className="route-stats">
              <span>{r.distance_mi} mi</span>
              <span>{hours(r.duration_min)}</span>
            </div>
            <div className="route-risk">
              <span style={{ color: riskColor(3) }}>{r.severe_miles} mi Severe</span>
              <span style={{ color: riskColor(2) }}>{r.high_miles} mi High</span>
              <span>avg {r.avg_risk}</span>
            </div>
            {recommended && (
              <div className="route-why">Chosen: {result.deciding_criterion}</div>
            )}
          </button>
        );
      })}
    </div>
  );
}
