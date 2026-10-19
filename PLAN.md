# Weather-aware truck routing

Spotter scores this take-home **40%** on route, weather, risk, and recommendation logic, and **40%** on map and heatmap smoothness. The other **20%** is code quality (15%) plus the README and Loom (5%).

The submission wins by making two things obvious:

1. Checkpoints are scored at the truck's **arrival hour**.
2. The heatmap is the same risk function across the corridor for each hour **after departure**, already in memory before the slider moves.

The winning route card says why it won, in miles.

## Evaluation

| Slice | Weight | What a strong submission shows |
| --- | ---: | --- |
| Routes, weather, risk, recommendation | 40% | Pure risk module, mile-weighted rank, arrival-hour weather, load upgrades, a test at every boundary |
| Map, heatmap, smoothness | 40% | One request, a slider that never refetches, readable routes on top of the heatmap, a reason sentence |
| Code quality | 15% | Thin views, a typed response, no scoring math in React |
| Docs and walkthrough | 5% | Assumptions, run steps, a six-minute Loom |

## Locked decisions

These are the ambiguities a reviewer will probe. They stay stable so the tests and the UI describe the same model.

| Decision | Rule |
| --- | --- |
| 10 / 25 / 50 miles | A control on the form. Default **25**. Always include the origin and the destination. |
| Shared band edges | Lower bound inclusive. A shared edge belongs to the **worse** band. 1.00 in/hr rain and 3.0 in/hr snow stay Severe. The next tick above that is No Travel. |
| Several conditions at once | Checkpoint risk is the **worst** of wind-with-load, rain, and snow. |
| Severe and high miles | Sum of route-segment lengths. A segment takes the worse of its endpoints. |
| No Travel | Its own rank key, **ahead of** Severe miles. |
| Average risk | Mile-weighted mean. Low 1, Moderate 2, High 3, Severe 4, No Travel 5. |
| Arrival weather | Nearest forecast hour to that checkpoint's ETA. ETA comes from the routing engine's step durations. |
| Heatmap clock | Hours after departure, 0 through 48, same classifier and the same load. |
| Missing forecast | Mark the point unknown. Leave it out of the average. Do not paint it Low. A route with no scored miles sorts after any scored route. |
| Fewer than three routes | Render what came back and say so. |

Wind bands are half-open so 34.9 mph stays Moderate and 35.0 mph is High. Rain and snow keep the printed top of Severe inclusive, because No Travel is strict greater-than.

## Risk model

Lives in `backend/routing/risk.py`. No HTTP. The view calls it. React displays the result.

### Weather bands

| Condition | Low | Moderate | High | Severe | No Travel |
| --- | --- | --- | --- | --- | --- |
| Wind | < 25 mph | 25 up to 35 | 35 up to 45 | 45 up to 55 | ≥ 55 mph |
| Rain | < 0.10 in/hr | 0.10 up to 0.25 | 0.25 up to 0.50 | 0.50 through 1.00 | > 1.00 |
| Snow | < 0.5 in/hr | 0.5 up to 1.0 | 1.0 up to 2.0 | 2.0 through 3.0 | > 3.0 |

### Load upgrades, wind only

| Wind | Load | Result |
| --- | --- | --- |
| ≥ 55 mph | Any load | No Travel |
| 45 mph up to 55 | > 30,000 lb | No Travel |
| 45 mph up to 55 | ≤ 30,000 lb | Severe |
| 35 mph up to 45 | > 40,000 lb | Severe |
| 35 mph up to 45 | ≤ 40,000 lb | High |

30,000 lb and 40,000 lb stay in the weather band. The upgrade is strict greater-than.

### Sort key, ascending

```text
(no_travel_miles, severe_miles, high_miles, avg_risk, duration_seconds)

avg_risk = sum(segment_miles * level) / sum(segment_miles)
level    = Low 1, Moderate 2, High 3, Severe 4, No Travel 5
segment  = worse of the two checkpoint levels
```

A route with no scored miles sorts after every scored route. Unknown miles are reported and left out of the average.

The reason sentence comes from the first key that differs.

> Route B has 0 severe miles. Route A has 37. It takes 14 minutes longer.

When every route has some No Travel miles, still recommend the least-bad one and say that none of the options is clear.

## Request path

The browser sends one payload. Django geocodes, routes, samples, fetches weather, scores, and returns routes plus 49 heatmap hours. The slider never starts a second request.

```text
Form → Geocode → Routes → Samples ─┐
                     └→ Corridor ──┴→ Forecast → Risk → Rank → Map
```

| Stage | Owner | Output |
| --- | --- | --- |
| Trip form | React | Origin, destination, departure, load pounds, sample miles |
| Geocode | Nominatim, or OpenRouteService when a key is set | Coordinates. Timezone comes from the Open-Meteo series at the origin |
| Routes | OpenRouteService if `ORS_API_KEY` is set, otherwise public OSRM | Up to three lines, distance, and per-step duration |
| Samples | Django | Mile 0, each interval, and the last mile, with an ETA |
| Corridor | Django | A band around the routes, capped near 140 points so the forecast stays fast |
| Forecast | Open-Meteo, batched and cached ~30 min | Hourly wind mph, rain, snow |
| Risk and rank | Pure Python | Checkpoint reasons, mile totals, winner, reason sentence |
| Map | MapLibre | Lines, dots, and a heatmap source that already holds every hour |

### Services

| Job | Choice | Note |
| --- | --- | --- |
| Routes | OpenRouteService `driving-hgv`, then `driving-car` | One key. Ask for two alternatives besides the primary. If the truck profile rejects alternatives, retry the car profile. |
| Routes without a key | Public OSRM | Lets the app run for local review. Document the limit: no truck restrictions, and the public server is rate-limited. |
| Weather | Open-Meteo | No key. Hourly `wind_speed_10m`, `rain`, and `snowfall`. Convert using the `hourly_units` field. Snow is often centimeters. |
| Map | MapLibre GL + OpenFreeMap | WebGL. Heatmap circles under the lines. Checkpoints above both. |

Sustained wind is the score. Gusts stay off the classifier so the numbers match the printed thresholds.

Departure is a wall time at the origin. Read the timezone from the origin forecast and place each ETA on the nearest forecast hour. Step durations drive the clock, not a single average speed for the whole trip.

## Screen

Desktop layout: a column about 380px for the form and three route cards, and a map filling the rest. The recommended card is first. Clicking a card and clicking a line select the same route.

| On screen | Behavior |
| --- | --- |
| Route cards | Duration, distance, no-travel miles, severe miles, high miles, average risk, and one sentence on the winner. |
| Risk strip | Merged segments, colored by risk, so the mile comparison is visible without hovering. |
| Checkpoint | Color by risk. Hover shows ETA, wind, rain, snow, and the reason, including the load upgrade when it fired. |
| Legend | Dots use arrival weather. The color wash is the corridor at the slider hour. |
| Slider | Hours after departure, 0 to 48. On input, swap a precomputed property. Do not call the network. |
| Layer order | Heatmap circles, then the other routes dimmed, then the selected route, then checkpoints for the selected route. |

## Tests

Table-driven, no network.

| Case | Expect |
| --- | --- |
| Wind 24.9, 25, 34.9, 35, 44.9, 45, 54.9, 55 | Low, Moderate, Moderate, High, High, Severe, Severe, No Travel |
| Rain 0.10, 0.25, 0.50, 1.00, 1.01 | Moderate, High, Severe, Severe, No Travel |
| Snow 0.5, 1.0, 2.0, 3.0, 3.1 | Moderate, High, Severe, Severe, No Travel |
| Wind 46 mph at 30,000 lb and at 30,001 lb | Severe, then No Travel |
| Wind 36 mph at 40,000 lb and at 40,001 lb | High, then Severe |
| Wind 55 mph at 10,000 lb | No Travel |
| Severe wind and light rain | Severe |
| 0 severe miles vs any severe miles | The route with 0 severe miles wins, even with a long High stretch |
| Identical risk, different duration | Shorter travel time wins |
| Heavy load upgrades a long High stretch into a longer Severe stretch than a snow route | The winner flips to the route with fewer severe miles |
| Checkpoint halfway on a 4-hour route | ETA matches the step-duration fraction |

## API

`POST /api/trips`

```json
{
  "origin": "Dallas, TX",
  "destination": "Chicago, IL",
  "departure": "2026-10-20T08:00",
  "load_lb": 42000,
  "sample_miles": 25
}
```

The response includes the origin timezone departure, up to three routes in rank order, checkpoint ETAs and reasons, merged segments, the recommended id, the reason sentence, the provider that produced the routes, and heatmap points with 49 risk labels each (hours 0 through 48).

## Repo shape

| Path | Responsibility |
| --- | --- |
| `backend/routing/risk.py` | Bands, load upgrades, worst condition, segments, rank, reason |
| `backend/routing/sampling.py` | Polyline miles and ETAs from step durations |
| `backend/routing/corridor.py` | Band points and the 250-point cap |
| `backend/routing/providers.py` | Nominatim, OpenRouteService, OSRM, Open-Meteo |
| `backend/routing/trip.py` | One function that builds the response |
| `backend/routing/views.py` | Parse input, call `build_trip`, map errors |
| `backend/routing/tests/` | Boundary tables and a pipeline test with fake providers |
| `frontend/src/` | Form, cards, MapLibre map, slider |
| `README.md` | Run, env vars, assumptions |

Dev: Vite proxies `/api` to Django on port 8000. Production can serve `frontend/dist` from the same Django process.

## Build order

1. **Risk module, tests, and a curl-able payload.** Finish this before polishing the map.
2. **Form, route cards, polylines, checkpoints, legend, and the slider.**
3. **README, deploy, Loom.** Open the live URL once before recording so a sleeping host is awake. If that morning is calm, keep the live trip short and let pytest show Severe, the load upgrades, and No Travel.

## Loom (about six minutes)

| Time | Show |
| --- | --- |
| 0:00 | The job of the app in one sentence, then the two clocks. |
| 0:30 | A live trip with a heavy load. Read the reason, including the mile counts. |
| 2:00 | Hover a late checkpoint. Its weather hour is the ETA. An earlier dot can disagree with the slider. |
| 3:15 | Scrub 0–48. The network panel stays quiet. |
| 4:15 | pytest the boundary table. |
| 5:15 | README assumptions: miles, worse band on a shared edge, No Travel sorted first. |
| 5:45 | Stop on the hosted URL. |

## Leave out

Accounts, saved trips, a routing engine of our own, multi-stop trips, and a play button on the slider. A truck profile is a retry after car alternatives already work. It is not worth a failed demo.
