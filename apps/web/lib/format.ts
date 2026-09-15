/**
 * Small, dependency-free presentation formatters. These are display
 * concerns only — the data layer under `data/` never formats values,
 * it just stores them (UTC timestamps, plain numbers), so formatting
 * choices can change without touching sample data or query helpers.
 */

/**
 * e.g. "10 Feb 2025, 6:00 am AEDT" — capture time shown in its station's
 * local time zone. Uses explicit field options rather than dateStyle/
 * timeStyle, since the Intl spec does not allow mixing those style
 * shorthands with timeZoneName.
 */
export function formatLocalDateTime(capturedAtUtc: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
    timeZone,
  }).format(new Date(capturedAtUtc));
}

/** e.g. "1 March 2018" — for date-only fields such as a station's operational start date. */
export function formatOperationalDate(isoDate: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(isoDate));
}

/** e.g. "34.4200° S, 150.8900° E" */
export function formatCoordinates(latitude: number, longitude: number): string {
  const latHemisphere = latitude < 0 ? "S" : "N";
  const lonHemisphere = longitude < 0 ? "W" : "E";
  return `${Math.abs(latitude).toFixed(4)}° ${latHemisphere}, ${Math.abs(longitude).toFixed(4)}° ${lonHemisphere}`;
}

/**
 * e.g. "2025-02-10" — the local calendar date (in the given time zone) a
 * UTC instant falls on. Used to group and filter observations by the
 * day a viewer in that time zone would actually see them on, which can
 * differ from the UTC calendar date.
 */
export function getLocalDateKey(capturedAtUtc: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone,
  }).formatToParts(new Date(capturedAtUtc));
  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${lookup.year}-${lookup.month}-${lookup.day}`;
}

/** Minutes since local midnight (0-1439) in the given time zone. */
export function getLocalMinutesOfDay(capturedAtUtc: string, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-AU", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).formatToParts(new Date(capturedAtUtc));
  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return Number(lookup.hour) * 60 + Number(lookup.minute);
}

/** e.g. "Wednesday 12 February 2025" — a day-group heading for a local date key. */
export function formatDayHeading(localDateKey: string): string {
  const [year, month, day] = localDateKey.split("-").map(Number);
  return new Intl.DateTimeFormat("en-AU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

/** e.g. "12 Feb" — a compact label for date-navigation links. */
export function formatShortDate(localDateKey: string): string {
  const [year, month, day] = localDateKey.split("-").map(Number);
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

/** e.g. "6:00 am" — a compact time-only label, for related-media chips. */
export function formatLocalTime(capturedAtUtc: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone,
  }).format(new Date(capturedAtUtc));
}

/** e.g. "1.2 MB" — a human-readable file size. */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) return `${kilobytes.toFixed(kilobytes < 10 ? 1 : 0)} KB`;
  const megabytes = kilobytes / 1024;
  return `${megabytes.toFixed(megabytes < 10 ? 1 : 0)} MB`;
}
