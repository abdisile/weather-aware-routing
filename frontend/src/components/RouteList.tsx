import { Badge } from "./ui/badge.tsx";
import { cn } from "@/lib/utils.ts";
import { formatClock, formatLoad, formatMeasure } from "../format.ts";
import { RISK_COLORS, RISK_LABELS, type Checkpoint, type RouteOption, type Segment, type TripResult } from "../types.ts";

type RouteListProps = {
  result: TripResult;
  selectedId: string;
  onSelect: (routeId: string) => void;
};

export function RouteList({ result, selectedId, onSelect }: RouteListProps) {
  const recommended = result.routes.find((route) => route.id === result.recommended_route_id);
  return (
    <div>
      <section className="border-b border-border px-5 py-4 sm:px-6">
        <p className="text-[11px] font-medium tracking-[0.14em] text-muted-foreground uppercase">Recommendation</p>
        <h2 className="mt-1 text-base font-medium">{recommended?.name ?? "Route"}</h2>
        <p className="mt-2 text-sm leading-relaxed">{result.recommendation_reason}</p>
        {result.route_note ? <p className="mt-2 text-sm text-muted-foreground">{result.route_note}</p> : null}
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{sourceLine(result)}</p>
      </section>
      <div className="flex flex-wrap gap-2 px-5 pt-4 sm:px-6">
        <Badge variant="outline">{formatLoad(result.load_lb)} load</Badge>
        <Badge variant="outline">Every {result.sample_miles} mi</Badge>
        <Badge variant="outline">{result.timezone}</Badge>
      </div>
      <p className="px-5 pt-4 text-sm text-muted-foreground sm:px-6">
        Select a route to draw it in blue and list the checkpoints that are above Low.
      </p>
      <div className="mt-3 border-t border-border">
        {result.routes.map((route, index) => (
          <RouteCard
            key={route.id}
            route={route}
            rank={index + 1}
            selected={route.id === selectedId}
            recommended={route.id === result.recommended_route_id}
            onSelect={onSelect}
          />
        ))}
      </div>
      <details className="border-t border-border px-5 py-3 text-sm sm:px-6">
        <summary className="cursor-pointer font-medium">How routes are ranked</summary>
        <ol className="mt-3 list-decimal space-y-1 pl-4 text-muted-foreground">
          <li>Fewest no-travel miles</li>
          <li>Fewest severe miles</li>
          <li>Fewest high miles</li>
          <li>Lowest average risk</li>
          <li>Shortest drive time</li>
        </ol>
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          Average risk scores Low as 1 and No Travel as 5. Miles with no forecast are left out of the average.
        </p>
      </details>
    </div>
  );
}

function RouteCard({
  route,
  rank,
  selected,
  recommended,
  onSelect,
}: {
  route: RouteOption;
  rank: number;
  selected: boolean;
  recommended: boolean;
  onSelect: (routeId: string) => void;
}) {
  const elevated = route.checkpoints.filter((checkpoint) => checkpoint.risk !== "low");
  return (
    <article className={cn("border-b border-l-[3px] border-border", selected ? "border-l-primary bg-accent" : "border-l-transparent")}>
      <button
        type="button"
        className="grid w-full gap-3 px-5 py-4 text-left focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none focus-visible:ring-inset sm:px-6"
        aria-pressed={selected}
        onClick={() => onSelect(route.id)}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={cn(
                "grid size-8 shrink-0 place-items-center border text-xs font-medium tabular-nums",
                selected ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground",
              )}
            >
              {rank}
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-medium">{route.name}</h3>
              {route.via ? <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">via {route.via}</p> : null}
            </div>
          </div>
          {recommended ? <Badge className="shrink-0">Recommended</Badge> : null}
        </div>
        <p className="text-xs font-medium text-primary">{selected ? "Showing on the map" : "Show on the map"}</p>
        <p className={cn("border-l-2 pl-3 text-sm leading-relaxed", recommended ? "border-primary" : "border-border")}>
          {route.rank_reason}
        </p>
        <dl className="grid grid-cols-2 gap-3">
          <Stat label="Drive time" value={formatClock(route.duration_seconds)} />
          <Stat label="Distance" value={`${route.distance_miles} mi`} />
        </dl>
        <RiskStrip segments={route.segments} />
        <dl className="grid grid-cols-4 gap-2 border-t border-border pt-3">
          <Stat label="No travel" value={`${route.no_travel_miles} mi`} />
          <Stat label="Severe" value={`${route.severe_miles} mi`} />
          <Stat label="High" value={`${route.high_miles} mi`} />
          <Stat label="Avg 1–5" value={route.average_risk === null ? "—" : route.average_risk.toFixed(2)} />
        </dl>
      </button>
      {selected ? (
        <div className="grid gap-3 border-t border-border px-5 py-3 sm:px-6">
          <div>
            <p className="text-sm font-medium">Checkpoints above Low</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Low samples stay on the map. This list is only the miles that need attention.
            </p>
          </div>
          {elevated.length === 0 ? (
            <p className="text-sm text-muted-foreground">Every sample on this route is Low.</p>
          ) : (
            elevated.map((checkpoint) => (
              <CheckpointRow key={`${checkpoint.mile}-${checkpoint.eta}`} checkpoint={checkpoint} />
            ))
          )}
        </div>
      ) : null}
    </article>
  );
}

function CheckpointRow({ checkpoint }: { checkpoint: Checkpoint }) {
  return (
    <div className="grid gap-1 border-t border-border pt-3">
      <div className="flex items-center gap-2 text-sm">
        <span className="size-2.5 shrink-0" style={{ background: RISK_COLORS[checkpoint.risk] }} />
        <strong className="font-medium">
          Mile {checkpoint.mile} · {RISK_LABELS[checkpoint.risk]}
        </strong>
        <span className="ml-auto text-muted-foreground tabular-nums">{checkpoint.eta_label}</span>
      </div>
      <p className="text-sm text-muted-foreground">{checkpoint.reasons.join(" · ")}</p>
      <p className="text-xs text-muted-foreground tabular-nums">
        Wind {formatMeasure(checkpoint.wind_mph, "mph")} · Rain {formatMeasure(checkpoint.rain_in_hr, "in/hr")} · Snow{" "}
        {formatMeasure(checkpoint.snow_in_hr, "in/hr")}
      </p>
    </div>
  );
}

function RiskStrip({ segments }: { segments: Segment[] }) {
  const total = segments.reduce((sum, segment) => sum + segment.miles, 0) || 1;
  const label = segments.map((segment) => `${RISK_LABELS[segment.risk]} ${segment.miles} miles`).join(", ");
  return (
    <div className="flex h-1.5 bg-muted" role="img" aria-label={label}>
      {segments.map((segment, index) => (
        <span
          key={`${segment.risk}-${index}`}
          style={{ width: `${(segment.miles / total) * 100}%`, background: RISK_COLORS[segment.risk] }}
        />
      ))}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-medium tracking-[0.12em] text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-1 text-sm font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function sourceLine(result: TripResult): string {
  if (result.routing_provider === "openrouteservice") {
    const profile = result.routing_profile === "driving-hgv" ? "truck profile and this load" : result.routing_profile;
    return `Routes from OpenRouteService, using the ${profile}.`;
  }
  if (result.routing_provider === "osrm") {
    return "Routes from the public driving service. It does not apply truck restrictions.";
  }
  return `Routes from ${result.routing_provider}, ${result.routing_profile}.`;
}
