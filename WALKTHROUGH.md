# Loom Walkthrough Script (5–10 min)

A suggested structure for the recording. Have the app running locally (or the hosted URL)
and the code open in your editor.

## 0:00 — Intro (30s)
- "This is a weather-aware truck routing app. A driver enters origin, destination, departure
  time, and load weight, and it recommends the safest of 3 routes by balancing weather risk
  and travel time."
- Mention stack in one line: React + Leaflet front end, Django + DRF back end, HERE routing,
  Open-Meteo weather.

## 0:30 — Live demo: plan a trip (2 min)
- Enter Denver → Kansas City, pick a departure, set load weight to 42,000 lb, sample every 25 mi.
- Click **Plan route**. Point out the 3 route cards and the **Recommended** badge with its
  reason ("Chosen: shortest travel time" / "fewest Severe miles", etc.).
- Hover/click a few **checkpoint markers**: show the ETA, wind/rain/snow values, risk level,
  and the human-readable reasons (including any load-rule escalation).
- Click an alternative route card to switch the highlighted route.

## 2:30 — Weather heatmap + forecast slider (1.5 min)
- Toggle **Weather heatmap** on.
- Drag the **0–48 h slider** and hit play; narrate how the corridor risk changes over the
  forecast window, and that this is real Open-Meteo data.

## 4:00 — The risk logic (2 min)  ← this is 40% of the grade, spend time here
- Open `backend/routing/core/risk.py`.
- Show the three `classify_*` functions and the threshold table; explain lower-bound-inclusive
  bands + No-Travel cutoffs (closing the 54→55 gap).
- Show `classify_checkpoint`: worst-of-three, then the two load overrides.
- Show `recommend()` and the lexicographic sort key matching the spec's priority order.
- Open `backend/routing/tests/test_risk.py` and run `pytest` — show boundary + load-rule tests
  passing (e.g. 38 mph + 45,000 lb → Severe; 48 mph + 31,000 lb → No Travel).

## 6:00 — Architecture note (1 min)
- `POST /api/plan` orchestration in `backend/routing/api/views.py`: geocode → truck routes →
  sample checkpoints + ETAs → one bulk weather call → classify → recommend → corridor heatmap.
- Mention: HERE key stays server-side; chose HERE over OpenRouteService because ORS caps
  alternative routes at ~100 km; keyless **demo mode** for running without a key.

## 7:00 — Wrap (30s)
- Recap: correctness-first risk engine with tests, smooth map + heatmap, clean separation.
- Point to the GitHub repo and hosted URL.

### Tips
- If you don't have a HERE key yet, demo mode still shows the full flow (note the banner).
- Keep the editor font large; pre-run `pytest` once so it's warm.
