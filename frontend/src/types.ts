export type SampleMiles = 10 | 25 | 50;

export type TripDraft = {
  origin: string;
  destination: string;
  departure: string;
  loadLb: string;
  sampleMiles: SampleMiles;
};

export type RiskLabel =
  | "low"
  | "moderate"
  | "high"
  | "severe"
  | "no_travel"
  | "unknown";

export type Segment = {
  miles: number;
  risk: RiskLabel;
};

export type Checkpoint = {
  mile: number;
  lat: number;
  lon: number;
  eta: string;
  eta_label: string;
  wind_mph: number | null;
  rain_in_hr: number | null;
  snow_in_hr: number | null;
  risk: RiskLabel;
  reasons: string[];
};

export type RouteOption = {
  id: string;
  name: string;
  via: string;
  distance_miles: number;
  duration_seconds: number;
  geometry: number[][];
  no_travel_miles: number;
  severe_miles: number;
  high_miles: number;
  moderate_miles: number;
  low_miles: number;
  unknown_miles: number;
  average_risk: number | null;
  segments: Segment[];
  checkpoints: Checkpoint[];
  rank_reason: string;
};

export type HeatmapPoint = {
  lat: number;
  lon: number;
  risk_by_hour: RiskLabel[];
};

export type TripResult = {
  origin: { label: string; lat: number; lon: number };
  destination: { label: string; lat: number; lon: number };
  departure: string;
  timezone: string;
  load_lb: number;
  sample_miles: SampleMiles;
  routing_provider: string;
  routing_profile: string;
  recommended_route_id: string;
  recommendation_reason: string;
  route_note: string | null;
  routes: RouteOption[];
  heatmap: { points: HeatmapPoint[] };
};

export const RISK_COLORS: Record<RiskLabel, string> = {
  low: "#178a4a",
  moderate: "#c49212",
  high: "#e06a14",
  severe: "#d23b32",
  no_travel: "#6b3cc9",
  unknown: "#8b939e",
};

export const RISK_LABELS: Record<RiskLabel, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
  no_travel: "No travel",
  unknown: "Unknown",
};
