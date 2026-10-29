import { useEffect, useRef } from "react";
import { fmtTime } from "../lib/risk.js";

export default function TimeSlider({ hours, hour, setHour, playing, setPlaying }) {
  const timer = useRef(null);

  useEffect(() => {
    if (!playing) return;
    timer.current = setInterval(() => {
      setHour((h) => (h >= hours.length - 1 ? 0 : h + 1));
    }, 350);
    return () => clearInterval(timer.current);
  }, [playing, hours.length, setHour]);

  const current = hours[hour];

  return (
    <div className="time-slider">
      <button className="play" onClick={() => setPlaying((p) => !p)}>
        {playing ? "❚❚" : "▶"}
      </button>
      <input
        type="range"
        min={0}
        max={hours.length - 1}
        value={hour}
        onChange={(e) => setHour(Number(e.target.value))}
      />
      <div className="time-label">
        +{current.offset}h · {fmtTime(current.iso)}
      </div>
    </div>
  );
}
