import { useEffect } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup, useMap } from "react-leaflet";
import HeatmapLayer from "./HeatmapLayer.jsx";
import { riskColor, riskLabel, fmtTime } from "../lib/risk.js";

function FitBounds({ geometry }) {
  const map = useMap();
  useEffect(() => {
    if (geometry?.length) map.fitBounds(geometry, { padding: [40, 40] });
  }, [map, geometry]);
  return null;
}

export default function MapView({ result, selectedRouteId, onSelectRoute, showHeat, hour }) {
  const selected = result.routes.find((r) => r.id === selectedRouteId) || result.routes[0];
  const corridorHour = result.corridor.hours[hour];

  return (
    <MapContainer center={[39, -98]} zoom={5} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Alternative routes (dimmed, clickable) */}
      {result.routes.map((r) =>
        r.id === selectedRouteId ? null : (
          <Polyline
            key={r.id}
            positions={r.geometry}
            pathOptions={{ color: "#64748b", weight: 3, opacity: 0.45, dashArray: "6 8" }}
            eventHandlers={{ click: () => onSelectRoute(r.id) }}
          />
        )
      )}

      {/* Selected route (bold) */}
      <Polyline positions={selected.geometry} pathOptions={{ color: "#4f46e5", weight: 5, opacity: 0.9 }} />
      <FitBounds geometry={selected.geometry} />

      {/* Checkpoints coloured by risk */}
      {!showHeat &&
        selected.checkpoints.map((c) => (
          <CircleMarker
            key={c.seq}
            center={[c.lat, c.lon]}
            radius={6}
            pathOptions={{ color: "#0f172a", weight: 1, fillColor: riskColor(c.level), fillOpacity: 0.95 }}
          >
            <Popup>
              <strong>Mile {Math.round(c.mile)}</strong> · {riskLabel(c.level)}
              <br />
              ETA: {fmtTime(c.eta)}
              <br />
              Wind {c.wind_mph} mph · Rain {c.rain_in} in/hr · Snow {c.snow_in} in/hr
              {c.reasons?.length ? (
                <ul className="reasons">
                  {c.reasons.map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                </ul>
              ) : null}
            </Popup>
          </CircleMarker>
        ))}

      {/* Corridor weather heatmap for the selected forecast hour */}
      <HeatmapLayer
        points={result.corridor.points}
        riskByPoint={corridorHour.risk_by_point}
        visible={showHeat}
      />
    </MapContainer>
  );
}
