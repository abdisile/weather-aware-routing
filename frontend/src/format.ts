export function defaultDeparture(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(8, 0, 0, 0);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function formatClock(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours && mins) return `${hours} hr ${mins} min`;
  if (hours) return `${hours} hr`;
  return `${mins} min`;
}

export function formatLoad(pounds: number): string {
  return `${Math.round(pounds).toLocaleString("en-US")} lb`;
}

export function formatMeasure(value: number | null, unit: string): string {
  if (value === null) return "—";
  return `${value} ${unit}`;
}
