import type { CoastSnapDataSource } from "@/data";

/**
 * The global footer's data notice. Station, camera and media records are
 * always synthetic sample data in this build. Only CoastSnap can be
 * catalogue-backed, so API mode describes exactly that and nothing more.
 *
 * It never claims production data: nothing in the frontend configuration
 * asserts that the catalogue is a production service. A production claim
 * would need an explicit signal from the API configuration, which doesn't
 * exist yet.
 */
export function getFooterDataNotice(source: CoastSnapDataSource): string {
  return source === "api"
    ? "Development build — station, camera and media records are synthetic sample data; CoastSnap observations are served by the AusCIN catalogue API."
    : "Development build — station, camera, media and CoastSnap records are synthetic sample data.";
}
