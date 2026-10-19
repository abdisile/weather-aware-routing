import { useEffect, useRef, useState, type ButtonHTMLAttributes } from "react";
import { scoreTrip } from "./api.ts";
import { cn } from "@/lib/utils.ts";
import { MapView } from "./components/MapView.tsx";
import { RouteList } from "./components/RouteList.tsx";
import { TripForm } from "./components/TripForm.tsx";
import { defaultDeparture } from "./format.ts";
import type { TripDraft, TripResult } from "./types.ts";

export default function App() {
  const [draft, setDraft] = useState<TripDraft>({
    origin: "Dallas, TX",
    destination: "Chicago, IL",
    departure: defaultDeparture(),
    loadLb: "42000",
    sampleMiles: 25,
  });
  const [result, setResult] = useState<TripResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hour, setHour] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<"trip" | "routes">("trip");
  const activeRequest = useRef<AbortController | null>(null);
  const asideRef = useRef<HTMLElement>(null);

  useEffect(() => {
    return () => activeRequest.current?.abort();
  }, []);

  async function compare() {
    const load = Number(draft.loadLb);
    if (!Number.isFinite(load)) {
      setError("Enter a load weight in pounds.");
      return;
    }
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError(null);
    try {
      const next = await scoreTrip(
        {
          origin: draft.origin.trim(),
          destination: draft.destination.trim(),
          departure: draft.departure,
          load_lb: load,
          sample_miles: draft.sampleMiles,
        },
        controller.signal,
      );
      setResult(next);
      setSelectedId(next.recommended_route_id);
      setHour(0);
      setPanel("routes");
      asideRef.current?.scrollTo({ top: 0 });
    } catch (caught) {
      if (controller.signal.aborted) return;
      const message = caught instanceof Error ? caught.message : "The trip could not be scored.";
      setError(message);
    } finally {
      if (activeRequest.current === controller) setLoading(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground lg:h-dvh lg:overflow-hidden">
      <header className="flex shrink-0 items-center justify-between bg-card px-5 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center bg-primary text-primary-foreground">
            <span className="font-serif text-xl leading-none italic">S</span>
          </span>
          <div className="leading-none">
            <p className="font-serif text-[26px] leading-none italic">Spotter</p>
            <p className="mt-1.5 text-[11px] tracking-[0.16em] text-muted-foreground uppercase">
              Weather-aware routing
            </p>
          </div>
        </div>
        <p className="hidden text-sm text-muted-foreground md:block">Trip, then ranked routes</p>
      </header>
      <div className="h-0.5 shrink-0 bg-primary" />
      <div className="lg:grid lg:min-h-0 lg:flex-1 lg:grid-cols-[440px_minmax(0,1fr)] lg:grid-rows-1">
        <aside ref={asideRef} className="border-border bg-card lg:min-h-0 lg:overflow-y-auto lg:border-r">
          <div className="sticky top-0 z-10 flex border-b border-border bg-card" role="tablist" aria-label="Steps">
            <StepTab selected={panel === "trip"} controls="trip-panel" onClick={() => setPanel("trip")}>
              1 · Trip
            </StepTab>
            <StepTab selected={panel === "routes"} controls="routes-panel" onClick={() => setPanel("routes")}>
              2 · Routes{result ? ` · ${result.routes.length}` : ""}
            </StepTab>
          </div>
          {panel === "trip" ? (
            <div id="trip-panel" role="tabpanel" className="px-5 py-5 sm:px-6">
              <p className="mb-5 text-sm leading-relaxed text-muted-foreground">
                Enter the haul. The app scores up to three routes using the weather at the truck&apos;s arrival.
              </p>
              <TripForm draft={draft} loading={loading} onChange={setDraft} onSubmit={() => void compare()} />
              {error ? (
                <p className="mt-4 border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive" role="alert">
                  {error}
                </p>
              ) : null}
            </div>
          ) : (
            <div id="routes-panel" role="tabpanel">
              {result && selectedId ? (
                <RouteList result={result} selectedId={selectedId} onSelect={setSelectedId} />
              ) : (
                <div className="px-5 py-8 sm:px-6">
                  <p className="text-sm font-medium">No routes yet</p>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {loading
                      ? "Sampling the forecast along each route. This can take a minute."
                      : "Compare a trip first. Ranked routes, the reason, and checkpoints will show up here."}
                  </p>
                  <button
                    type="button"
                    className="mt-4 text-sm font-medium text-primary"
                    onClick={() => setPanel("trip")}
                  >
                    Back to the trip
                  </button>
                </div>
              )}
            </div>
          )}
        </aside>
        <MapView
          result={result}
          selectedId={selectedId}
          hour={hour}
          loading={loading}
          onSelect={setSelectedId}
          onHour={setHour}
        />
      </div>
    </div>
  );
}

function StepTab({
  selected,
  controls,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { selected: boolean; controls: string }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      aria-controls={controls}
      className={cn(
        "h-11 flex-1 border-b-2 text-sm font-medium",
        selected ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
        className,
      )}
      {...props}
    />
  );
}
