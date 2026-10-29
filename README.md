# Weather-Aware Truck Routing

A React + Django web app that helps a truck driver choose the **safest** route based on
weather, load weight, and travel time. The driver enters an origin, destination, departure
time, and load weight; the app generates 3 route options, samples weather at checkpoints
along each route using the truck's **estimated arrival time at that point**, scores weather
risk against fixed threshold/load rules, recommends the best route, and visualizes
everything on a map plus a corridor weather heatmap with a 0–48 hour forecast slider.

## Submission links

| Deliverable | Link |
|---|---|
| GitHub repository | https://github.com/atreyakamat/weather-aware-truck-routing |
| Hosted application | _add after deploying_ |
| Loom walkthrough (5–10 min) | _add after recording — see [WALKTHROUGH.md](WALKTHROUGH.md)_ |

## Features

- **3 route options** between origin and destination (HERE truck routing).
- **Checkpoint weather sampling** every 10 / 25 / 50 miles, at each checkpoint's ETA.
- **Risk engine** implementing the provided wind/rain/snow thresholds + load-weight rules.
- **Recommendation** balancing weather risk and travel time, with an explained reason.
- **Interactive map** (Leaflet/OSM): all routes, risk-colored checkpoints with popups
  (ETA, wind/rain/snow, risk reasons), and recommended-route highlighting.
- **Weather heatmap** along the trip corridor with a 0–48 h forecast slider (+ play).
- **Keyless demo mode** so the app runs end-to-end without a routing key (see below).

## Architecture

```
Browser (React + Leaflet) ──POST /api/plan──► Django + DRF
                                                ├─ HERE Geocode   (origin/dest → coords)
                                                ├─ HERE Routes    (truck, alternatives → 3 routes)
                                                ├─ core/sampling  (walk polyline → checkpoints + ETAs)
                                                ├─ Open-Meteo      (bulk hourly weather per checkpoint)
                                                ├─ core/risk       (classify + load rules + aggregates)
                                                └─ recommend()     (rank routes)
◄───────────── JSON: routes[], recommended_id, corridor heatmap data ─────────────┘
```

All domain logic lives in **pure, unit-tested** functions (`backend/routing/core/`), and all
keyed API calls are **proxied through Django** so the HERE key never reaches the browser.

### Why these APIs

- **HERE Routing v8** — true `transportMode=truck` with `alternatives`, and it handles long
  multi-hour routes. (OpenRouteService has a free truck profile too, but it **caps alternative
  routes at ~100 km straight-line**, which would make long-haul demos impossible — so HERE.)
- **Open-Meteo** — keyless hourly forecast (0–48 h+), returns `wind_speed_10m`, `rain`, and
  `snowfall`, with unit params (`wind_speed_unit=mph`, `precipitation_unit=inch`), and accepts
  **many coordinates per request** — one call covers all checkpoints.
- **Leaflet + OpenStreetMap** — token-free map tiles; `leaflet.heat` for the heatmap.

## Risk rules

Each checkpoint is classified on wind, rain, and snow; the **worst** of the three is taken,
then **load overrides** are applied. Bands are lower-bound-inclusive with explicit No-Travel
cutoffs (this closes the gaps in the printed ranges, e.g. wind 54→55). Implemented in
[`backend/routing/core/risk.py`](backend/routing/core/risk.py).

| Metric | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | `<25` | `25–<35` | `35–<45` | `45–<55` | `≥55` |
| Rain (in/hr) | `<0.10` | `0.10–<0.25` | `0.25–<0.50` | `0.50–≤1.00` | `>1.00` |
| Snow (in/hr) | `<0.5` | `0.5–<1.0` | `1.0–<2.0` | `2.0–≤3.0` | `>3.0` |

**Load overrides** (final = worst of base and override):
- wind `≥55` → No Travel (any load).
- wind `45–54` **and** load `>30,000 lb` → No Travel.
- wind `35–44` **and** load `>40,000 lb` → Severe.

**Recommendation** ranks routes lexicographically (lower is better) in the spec's priority
order: `(has No-Travel, severe miles, high miles, average risk, travel time)`. The response
includes the *deciding criterion* so the UI can explain why a route was chosen.

## Demo mode (no API key required)

If `HERE_API_KEY` is **unset** (or a request includes `"demo": true`), the backend geocodes
via Open-Meteo's free geocoder and **synthesizes** 3 route variants (direct + north/south
detours), while still fetching **real** weather. This keeps the app fully runnable and
recordable without a routing key, and acts as a graceful fallback. Set `HERE_API_KEY` to get
real truck-legal routing. The UI shows a "Demo mode" note when active.

## Local setup

### Backend (Django)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optionally set HERE_API_KEY; blank = demo mode
python manage.py runserver 8000
```

> Note: `departure` is sent without a timezone and is interpreted as **UTC** (`TIME_ZONE=UTC`).
> No database is used — the service is stateless.

### Frontend (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_BASE_URL defaults to http://localhost:8000
npm run dev                     # http://localhost:5173
```

## Testing

```bash
cd backend && source .venv/bin/activate
pytest
```

Covers the risk-engine band boundaries and load overrides, recommendation tie-breaks, the
sampling/ETA math, and an end-to-end `POST /api/plan` test with HERE + Open-Meteo mocked.

## API

`POST /api/plan`

```jsonc
// request
{
  "origin": "Denver, CO",
  "destination": "Kansas City, MO",
  "departure": "2026-10-30T08:00:00",   // ISO-8601, treated as UTC
  "load_weight_lb": 42000,
  "sample_interval_miles": 25,          // 10 | 25 | 50
  "demo": false                          // optional; force synthetic routes
}
```

Response: `recommended_id`, `deciding_criterion`, `demo_mode`, `routes[]` (geometry,
distance/duration, `severe_miles`/`high_miles`/`avg_risk`/`has_no_travel`, and
`checkpoints[]` with ETA, wind/rain/snow, risk `level` + `reasons`), and `corridor`
(points + per-hour `risk_by_point` for the 0–48 h heatmap). `GET /api/health` → `{"status":"ok"}`.

## Deployment

- **Backend → Render**: push to GitHub, create a Blueprint from [`render.yaml`](render.yaml).
  Set `HERE_API_KEY` (optional) and `CORS_ALLOWED_ORIGINS` (your Vercel URL) in the dashboard.
- **Frontend → Vercel**: import the repo, set **Root Directory = `frontend`**, and set
  `VITE_API_BASE_URL` to the Render URL. [`frontend/vercel.json`](frontend/vercel.json) handles
  the Vite build + SPA rewrites.

## Project structure

```
backend/
  config/            # Django settings, urls, wsgi
  routing/
    core/risk.py     # PURE risk engine (classify, load rules, aggregate, recommend)
    core/sampling.py # PURE polyline walk + ETA
    services/here.py # HERE geocode + truck routes (flexible-polyline decode)
    services/weather.py  # Open-Meteo bulk hourly + cache
    services/demo.py # keyless fallback provider
    api/             # DRF view + serializer + urls
    tests/           # pytest: risk, sampling, plan view
frontend/
  src/components/    # PlanForm, MapView, HeatmapLayer, RouteCards, TimeSlider
  src/lib/           # api client, risk colors
```

## License

MIT — see [LICENSE](LICENSE).
