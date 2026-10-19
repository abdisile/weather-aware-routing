import type { SampleMiles, TripResult } from "./types.ts";

export type TripInput = {
  origin: string;
  destination: string;
  departure: string;
  load_lb: number;
  sample_miles: SampleMiles;
};

export async function scoreTrip(input: TripInput, signal?: AbortSignal): Promise<TripResult> {
  let response: Response;
  try {
    response = await fetch("/api/trips/", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
      signal,
    });
  } catch (caught) {
    if (isAbort(caught)) throw caught;
    throw new Error("The trip could not be scored. Check that the API is running.");
  }

  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(errorMessage(payload));
  }
  if (!isTripResult(payload)) {
    throw new Error("The trip response was not in the expected shape.");
  }
  return payload;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function errorMessage(payload: unknown): string {
  if (typeof payload === "object" && payload !== null && "error" in payload) {
    const message = payload.error;
    if (typeof message === "string" && message) return message;
  }
  return "The trip could not be scored.";
}

function isTripResult(payload: unknown): payload is TripResult {
  if (typeof payload !== "object" || payload === null) return false;
  const record = payload as Record<string, unknown>;
  const heatmap = record.heatmap;
  const points =
    typeof heatmap === "object" && heatmap !== null && "points" in heatmap ? heatmap.points : null;
  return typeof record.recommended_route_id === "string" && Array.isArray(record.routes) && Array.isArray(points);
}

function isAbort(caught: unknown): boolean {
  return caught instanceof DOMException && caught.name === "AbortError";
}
