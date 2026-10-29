import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

// Renders a leaflet.heat layer for the corridor at a given forecast hour.
// Intensity = risk level normalised to 0..1, so Severe/No-Travel glow hottest.
export default function HeatmapLayer({ points, riskByPoint, visible }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    if (!visible || !points?.length) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }
    const heatPoints = points.map(([lat, lon], i) => [lat, lon, (riskByPoint[i] ?? 0) / 4]);
    if (!layerRef.current) {
      layerRef.current = L.heatLayer(heatPoints, {
        radius: 34,
        blur: 22,
        maxZoom: 9,
        minOpacity: 0.35,
        gradient: { 0.0: "#22c55e", 0.25: "#eab308", 0.5: "#f97316", 0.75: "#ef4444", 1.0: "#1f2937" },
      }).addTo(map);
    } else {
      layerRef.current.setLatLngs(heatPoints);
    }
  }, [map, points, riskByPoint, visible]);

  useEffect(() => () => {
    if (layerRef.current) map.removeLayer(layerRef.current);
  }, [map]);

  return null;
}
