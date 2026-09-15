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
