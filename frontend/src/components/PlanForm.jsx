import { useState } from "react";

function defaultDeparture() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(8, 0, 0, 0);
  // yyyy-MM-ddThh:mm for datetime-local
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function PlanForm({ onSubmit, loading }) {
  const [origin, setOrigin] = useState("Denver, CO");
  const [destination, setDestination] = useState("Kansas City, MO");
  const [departure, setDeparture] = useState(defaultDeparture());
  const [loadWeight, setLoadWeight] = useState(42000);
  const [interval, setInterval] = useState(25);

  const submit = (e) => {
    e.preventDefault();
    onSubmit({
      origin,
      destination,
      departure: `${departure}:00`,
      load_weight_lb: Number(loadWeight),
      sample_interval_miles: Number(interval),
    });
  };

  return (
    <form className="plan-form" onSubmit={submit}>
      <label>
        Origin
        <input value={origin} onChange={(e) => setOrigin(e.target.value)} required placeholder="City or address" />
      </label>
      <label>
        Destination
        <input value={destination} onChange={(e) => setDestination(e.target.value)} required placeholder="City or address" />
      </label>
      <label>
        Departure
        <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
      </label>
      <label>
        Load weight (lb)
        <input type="number" min="0" step="500" value={loadWeight} onChange={(e) => setLoadWeight(e.target.value)} required />
      </label>
      <label>
        Sample every
        <select value={interval} onChange={(e) => setInterval(e.target.value)}>
          <option value={10}>10 miles</option>
          <option value={25}>25 miles</option>
          <option value={50}>50 miles</option>
        </select>
      </label>
      <button type="submit" disabled={loading}>
        {loading ? "Planning…" : "Plan route"}
      </button>
    </form>
  );
}
