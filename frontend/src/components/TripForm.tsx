import type { FormEvent, ReactNode } from "react";
import { Clock3, Flag, Loader2, MapPin, Weight } from "lucide-react";
import { Button } from "./ui/button.tsx";
import { Input } from "./ui/input.tsx";
import { Label } from "./ui/label.tsx";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group.tsx";
import type { SampleMiles, TripDraft } from "../types.ts";

const INTERVALS: SampleMiles[] = [10, 25, 50];

type TripFormProps = {
  draft: TripDraft;
  loading: boolean;
  onChange: (draft: TripDraft) => void;
  onSubmit: () => void;
};

export function TripForm({ draft, loading, onChange, onSubmit }: TripFormProps) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  function setInterval(value: string) {
    if (value === "10" || value === "25" || value === "50") {
      onChange({ ...draft, sampleMiles: Number(value) as SampleMiles });
    }
  }

  return (
    <form className="grid gap-5" onSubmit={submit}>
      <Field icon={<MapPin className="size-3.5" />} label="Origin" htmlFor="origin">
        <Input
          id="origin"
          value={draft.origin}
          onChange={(event) => onChange({ ...draft, origin: event.target.value })}
          placeholder="Dallas, TX"
          autoComplete="off"
          required
        />
      </Field>
      <Field icon={<Flag className="size-3.5" />} label="Destination" htmlFor="destination">
        <Input
          id="destination"
          value={draft.destination}
          onChange={(event) => onChange({ ...draft, destination: event.target.value })}
          placeholder="Chicago, IL"
          autoComplete="off"
          required
        />
      </Field>
      <Field icon={<Clock3 className="size-3.5" />} label="Departure" htmlFor="departure" hint="Clock time where the truck starts.">
        <Input
          id="departure"
          type="datetime-local"
          value={draft.departure}
          onChange={(event) => onChange({ ...draft, departure: event.target.value })}
          required
        />
      </Field>
      <Field
        icon={<Weight className="size-3.5" />}
        label="Load weight"
        htmlFor="load"
        hint="Wind at 55 mph or more is No Travel at any load. Above 30,000 lb, 45–54 mph becomes No Travel. Above 40,000 lb, 35–44 mph becomes Severe."
      >
        <div className="flex">
          <Input
            id="load"
            className="border-r-0"
            type="number"
            min={0}
            max={200000}
            step={500}
            value={draft.loadLb}
            onChange={(event) => onChange({ ...draft, loadLb: event.target.value })}
            required
          />
          <span className="grid place-items-center border border-input bg-muted px-3 text-sm text-muted-foreground">lb</span>
        </div>
      </Field>
      <div className="grid gap-2">
        <Label id="sample-label">Sample weather every</Label>
        <ToggleGroup
          type="single"
          value={String(draft.sampleMiles)}
          onValueChange={setInterval}
          aria-labelledby="sample-label"
        >
          {INTERVALS.map((miles) => (
            <ToggleGroupItem key={miles} value={String(miles)}>
              {miles} mi
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Each sample uses the forecast at the truck&apos;s arrival. The start and the end are always included.
        </p>
      </div>
      <Button className="w-full" size="lg" type="submit" disabled={loading}>
        {loading ? <Loader2 className="size-4 animate-spin" /> : null}
        {loading ? "Scoring routes" : "Compare routes"}
      </Button>
    </form>
  );
}

function Field({
  icon,
  label,
  htmlFor,
  hint,
  children,
}: {
  icon: ReactNode;
  label: string;
  htmlFor: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <Label htmlFor={htmlFor}>{label}</Label>
      </div>
      {children}
      {hint ? <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
