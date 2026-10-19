import { useEffect, useRef } from "react";
import type { DataDrivenPropertyValueSpecification } from "@maplibre/maplibre-gl-style-spec";
import { LngLatBounds, Map, NavigationControl, Popup, setWorkerUrl } from "maplibre-gl";
import type { GeoJSONSource } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { Card } from "./ui/card.tsx";
import { Slider } from "./ui/slider.tsx";
import { RISK_COLORS, RISK_LABELS, type RiskLabel, type TripResult } from "../types.ts";

setWorkerUrl(maplibreWorkerUrl);

const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

type MapViewProps = {
  result: TripResult | null;
  selectedId: string | null;
  hour: number;
  loading: boolean;
  onSelect: (routeId: string) => void;
  onHour: (hour: number) => void;
};

export function MapView({ result, selectedId, hour, loading, onSelect, onHour }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const readyRef = useRef(false);
  const frameRef = useRef(0);
  const fittedRef = useRef<TripResult | null>(null);
  const propsRef = useRef({ result, selectedId, hour, onSelect });
  propsRef.current = { result, selectedId, hour, onSelect };

  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;

    const map = new Map({
      container,
      style: STYLE_URL,
      center: [-98.5, 39.5],
      zoom: 3.4,
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    const popup = new Popup({ closeButton: false, closeOnClick: false, offset: 16, className: "spotter-popup" });

    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container);

    map.on("load", () => {
      addLayers(map);
      readyRef.current = true;
      map.resize();
      paint(map, propsRef.current.result, propsRef.current.selectedId, propsRef.current.hour, fittedRef);

      map.on("click", "routes", (event) => {
        const id = event.features?.[0]?.properties?.id;
        if (typeof id === "string") propsRef.current.onSelect(id);
      });
      map.on("mouseenter", "routes", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "routes", () => {
        map.getCanvas().style.cursor = "";
      });
      map.on("mousemove", "checkpoints", (event) => {
        const feature = event.features?.[0];
        const properties = feature?.properties;
        if (!properties) return;
        map.getCanvas().style.cursor = "pointer";
        popup.setLngLat(event.lngLat).setHTML(popupHtml(properties)).addTo(map);
      });
      map.on("mouseleave", "checkpoints", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
    });

    mapRef.current = map;
    return () => {
      cancelAnimationFrame(frameRef.current);
      observer.disconnect();
      popup.remove();
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(() => {
      paint(map, result, selectedId, hour, fittedRef);
    });
  }, [result, selectedId, hour]);

  const selected = result?.routes.find((route) => route.id === selectedId);

  return (
    <div className="map-wrap h-[560px] lg:h-full">
      <div ref={containerRef} className="h-full w-full" />
      <Card className="absolute top-4 left-4 z-10 max-w-xs px-4 py-3">
        {selected ? (
          <>
            <p className="text-[11px] font-medium tracking-[0.14em] text-muted-foreground uppercase">On the map</p>
            <p className="mt-1 text-sm font-medium">{selected.name}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Blue line and dots are this route. Click another line to switch.
            </p>
          </>
        ) : (
          <>
            <p className="text-sm font-medium">{loading ? "Scoring the trip" : "How to read the map"}</p>
            <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs leading-relaxed text-muted-foreground">
              <li>Dots are weather at the truck&apos;s arrival.</li>
              <li>The wash is the corridor at the slider hour.</li>
              <li>The blue line is the route you select.</li>
            </ol>
          </>
        )}
      </Card>
      <div className="pointer-events-none absolute inset-x-3 bottom-3 z-10 grid gap-2">
        <Card className="pointer-events-auto flex w-fit flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2">
          <span className="text-[11px] font-medium tracking-[0.14em] text-muted-foreground uppercase">Risk</span>
          {(["low", "moderate", "high", "severe", "no_travel"] as RiskLabel[]).map((risk) => (
            <span key={risk} className="inline-flex items-center gap-2 text-xs text-foreground">
              <span className="size-2.5" style={{ background: RISK_COLORS[risk] }} />
              {RISK_LABELS[risk]}
            </span>
          ))}
        </Card>
        <Card className="pointer-events-auto grid gap-2 px-4 py-3">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium">Corridor forecast</span>
            <span className="text-sm font-medium tabular-nums">{hour === 0 ? "At departure" : `${hour} h later`}</span>
          </div>
          <Slider
            aria-label="Hours after departure"
            min={0}
            max={48}
            step={1}
            value={[hour]}
            disabled={!result}
            onValueChange={(value) => onHour(value[0] ?? 0)}
          />
          <div className="flex justify-between text-[10px] text-muted-foreground tabular-nums">
            <span>0h</span>
            <span>24h</span>
            <span>48h</span>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {result
              ? "Moving this recolors the wash only. The dots stay on the truck's arrival."
              : "This slider turns on after a trip is scored. It does not call the server."}
          </p>
        </Card>
      </div>
    </div>
  );
}

function addLayers(map: Map) {
  const empty = { type: "FeatureCollection" as const, features: [] };
  map.addSource("heatmap", { type: "geojson", data: empty });
  map.addLayer({
    id: "heatmap",
    type: "circle",
    source: "heatmap",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 10, 6, 22, 10, 40],
      "circle-color": riskColorExpression(),
      "circle-opacity": 0.45,
      "circle-blur": 0.35,
    },
  });
  map.addSource("routes", { type: "geojson", data: empty });
  map.addLayer({
    id: "routes",
    type: "line",
    source: "routes",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ["case", ["==", ["get", "selected"], 1], "#1f4fd8", "#c5cad3"],
      "line-width": ["case", ["==", ["get", "selected"], 1], 5, 3],
      "line-opacity": ["case", ["==", ["get", "selected"], 1], 0.95, 0.75],
    },
  });
  map.addSource("checkpoints", { type: "geojson", data: empty });
  map.addLayer({
    id: "checkpoints",
    type: "circle",
    source: "checkpoints",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 6, 6, 8, 9, 11],
      "circle-color": riskColorExpression(),
      "circle-stroke-width": 1.25,
      "circle-stroke-color": "#ffffff",
    },
  });
}

function paint(
  map: Map,
  result: TripResult | null,
  selectedId: string | null,
  hour: number,
  fittedRef: { current: TripResult | null },
) {
  setSource(map, "heatmap", heatmapCollection(result, hour));
  setSource(map, "routes", routeCollection(result, selectedId));
  setSource(map, "checkpoints", checkpointCollection(result, selectedId));
  if (result && fittedRef.current !== result) {
    fittedRef.current = result;
    const bounds = new LngLatBounds();
    for (const route of result.routes) {
      for (const pair of route.geometry) {
        const lon = pair[0];
        const lat = pair[1];
        if (lon !== undefined && lat !== undefined) bounds.extend([lon, lat]);
      }
    }
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 56, duration: 700, maxZoom: 8 });
    }
  }
}

function setSource(map: Map, id: string, data: GeoJSON.FeatureCollection) {
  const source = map.getSource(id) as GeoJSONSource | undefined;
  source?.setData(data);
}

function heatmapCollection(result: TripResult | null, hour: number): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: (result?.heatmap.points ?? []).map((point) => ({
      type: "Feature" as const,
      properties: { risk: point.risk_by_hour[hour] ?? "unknown" },
      geometry: { type: "Point" as const, coordinates: [point.lon, point.lat] },
    })),
  };
}

function routeCollection(result: TripResult | null, selectedId: string | null): GeoJSON.FeatureCollection {
  const routes = result?.routes ?? [];
  const ordered = [
    ...routes.filter((route) => route.id !== selectedId),
    ...routes.filter((route) => route.id === selectedId),
  ];
  return {
    type: "FeatureCollection",
    features: ordered.map((route) => ({
      type: "Feature" as const,
      properties: { id: route.id, selected: route.id === selectedId ? 1 : 0 },
      geometry: { type: "LineString" as const, coordinates: route.geometry },
    })),
  };
}

function checkpointCollection(result: TripResult | null, selectedId: string | null): GeoJSON.FeatureCollection {
  const route = result?.routes.find((item) => item.id === selectedId);
  return {
    type: "FeatureCollection",
    features: (route?.checkpoints ?? []).map((checkpoint) => ({
      type: "Feature" as const,
      properties: {
        risk: checkpoint.risk,
        mile: checkpoint.mile,
        eta: checkpoint.eta_label,
        reasons: checkpoint.reasons.join(" · "),
        wind: checkpoint.wind_mph,
        rain: checkpoint.rain_in_hr,
        snow: checkpoint.snow_in_hr,
      },
      geometry: { type: "Point" as const, coordinates: [checkpoint.lon, checkpoint.lat] },
    })),
  };
}

function riskColorExpression(): DataDrivenPropertyValueSpecification<string> {
  const expression: unknown[] = ["match", ["get", "risk"]];
  for (const [risk, color] of Object.entries(RISK_COLORS)) {
    expression.push(risk, color);
  }
  expression.push(RISK_COLORS.unknown);
  return expression as DataDrivenPropertyValueSpecification<string>;
}

function popupHtml(properties: GeoJSON.GeoJsonProperties): string {
  const record = properties ?? {};
  const risk = String(record.risk ?? "unknown") as RiskLabel;
  const label = RISK_LABELS[risk] ?? "Unknown";
  const color = RISK_COLORS[risk] ?? RISK_COLORS.unknown;
  return `
    <div class="popup">
      <strong style="display:flex;align-items:center;gap:8px"><span style="width:8px;height:8px;background:${color};display:inline-block"></span>Mile ${escapeHtml(String(record.mile ?? ""))} · ${escapeHtml(label)}</strong>
      <div>${escapeHtml(String(record.eta ?? ""))}</div>
      <div>${escapeHtml(String(record.reasons ?? ""))}</div>
      <div class="popup-readings">Wind ${escapeHtml(reading(record.wind, "mph"))} · Rain ${escapeHtml(reading(record.rain, "in/hr"))} · Snow ${escapeHtml(reading(record.snow, "in/hr"))}</div>
    </div>
  `;
}

function reading(value: unknown, unit: string): string {
  if (value === null || value === undefined || value === "") return "—";
  return `${value} ${unit}`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character] ?? character;
  });
}
