# Weather-aware truck routing

A React and Django app that compares up to three driving routes for a truck. Each route is sampled along the miles, the weather is read at the truck's arrival time, and the routes are ranked with the load in mind.

The build plan, including the band edges and the sort key, is in [PLAN.md](PLAN.md).

## Run locally

From the repo root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Start the API:

```powershell
.\.venv\Scripts\python backend\manage.py runserver
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to Django on port 8000.

`pytest` runs from the repo root:

```powershell
.\.venv\Scripts\python -m pytest backend -q
```

## Routing key

Without `ORS_API_KEY`, routes come from the public OSRM server and geocoding comes from Nominatim. That path has no truck restrictions and the public server is rate-limited.

With a free [OpenRouteService](https://openrouteservice.org/dev/#/signup) key in `.env`, the API tries the HGV profile (including vehicle weight) and falls back to the car profile if alternatives are rejected. A rejected key is reported. It is not silently swapped for OSRM.

```text
ORS_API_KEY=your-key
```

Weather is Open-Meteo. No key. Wind, rain, and snow are converted with the `hourly_units` field on the response. Snow is often reported in centimeters.

## Assumptions

- 10, 25, and 50 miles are a sampling control. The default is 25. The origin and destination are always included.
- A shared edge between two printed bands takes the worse class. 1.00 in/hr of rain and 3.0 in/hr of snow stay Severe.
- A checkpoint is the worst of wind-with-load, rain, and snow. A missing value is unknown, not calm.
- Severe, high, and no-travel exposure are miles along the route. A segment takes the worse endpoint.
- Sort order is no-travel miles, severe miles, high miles, mile-weighted average risk, then travel time. No Travel is sorted first. A route with no scored miles sorts after a route that has weather.
- Checkpoint weather is the forecast hour nearest that checkpoint's ETA. ETAs follow the routing engine's step durations. Departure is local time at the origin.
- The slider is hours after departure, 0 through 48. It uses the same risk function and the same load. The response already contains every hour, so moving the slider does not call the network.
- Dots on the map follow the truck. The color wash is the corridor at the slider hour.

## API

`POST /api/trips/`

```json
{
  "origin": "Dallas, TX",
  "destination": "Chicago, IL",
  "departure": "2026-10-20T08:00",
  "load_lb": 42000,
  "sample_miles": 25
}
```

`GET /api/health/` returns `{ "status": "ok" }`.

## Deploy

The app is a Django project with the React build served from the same host. Vercel detects `backend/manage.py` and runs the API as one function. Scoring is allowed up to five minutes, which covers the weather fetch.

Set `ORS_API_KEY` in the Vercel project. Without it, routes come from the public driving service. `DJANGO_SECRET_KEY` should be set there too. Do not commit `.env`.
