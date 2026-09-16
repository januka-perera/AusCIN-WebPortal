import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ObservationThumbnail } from "@/components/ui/observation-thumbnail";
import { SectionHeading } from "@/components/ui/section-heading";
import {
  getAllCameras,
  getAllStations,
  getLatestObservationPerStation,
  type Camera,
  type Station,
} from "@/data";
import { formatLocalDateTime } from "@/lib/format";
import { formatMediaTypeLabel } from "@/lib/observation-badge";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/site-config";

const capabilities = [
  {
    title: "Browse by station",
    description:
      "Move from a national list to a single station — its location, state or territory, cameras, lidar coverage and current operating status.",
  },
  {
    title: "Filter by camera and time",
    description:
      "Step through a station's archive by date range, time of day and camera to compare conditions hour by hour.",
  },
  {
    title: "Read the capture metadata",
    description:
      "Every image, composite and time-lapse keeps its station, camera, capture time in UTC, local time zone and processing status.",
  },
  {
    title: "Download permitted files",
    description:
      "Download the original file where its publication status allows it — useful for reporting, coastal-management work or further analysis.",
  },
];

export default function Home() {
  const stations = getAllStations();
  const cameras = getAllCameras();
  const stationById = new Map<string, Station>(stations.map((station) => [station.id, station]));
  const cameraById = new Map<string, Camera>(cameras.map((camera) => [camera.id, camera]));
  const latestObservations = getLatestObservationPerStation();

  return (
    <>
      <section className="border-b border-border bg-surface">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 sm:py-24 lg:grid-cols-[3fr_2fr] lg:items-center lg:gap-16">
          <div>
            <p className="text-meta uppercase tracking-label text-accent">
              Coastal observation archive
            </p>
            <h1 className="mt-4 font-display text-display-md text-foreground sm:text-display-lg">
              Browse coastal observations by station, camera and capture time.
            </h1>
            <p className="mt-6 max-w-xl text-body text-muted">
              AusCIN brings together fixed coastal cameras, lidar reference stations, existing
              camera infrastructure and CoastSnap observations in one searchable archive. Every
              image and video keeps its station, camera, capture time and processing status, with
              timestamps stored in UTC and shown in the station&apos;s local time zone.
            </p>
            <div className="mt-8">
              <Button href="/stations">
                Explore stations
                <span aria-hidden="true">&rarr;</span>
              </Button>
            </div>
          </div>

          <div className="flex justify-center lg:justify-end">
            <Image
              src="/brand/auscin-logo.png"
              alt={`${SITE_NAME} — ${SITE_TAGLINE} logo`}
              width={961}
              height={1264}
              className="h-72 w-auto sm:h-80"
              priority
            />
          </div>
        </div>
      </section>

      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <SectionHeading
            eyebrow="Archive structure"
            title="How AusCIN organises coastal imagery"
            description="Every record is tied to a station, a camera and a capture time — the three things you can always filter by."
          />
          <dl className="mt-8 grid gap-8 sm:grid-cols-2">
            {capabilities.map((item) => (
              <div key={item.title} className="border-t border-border pt-4">
                <dt className="font-display text-heading-md text-foreground">{item.title}</dt>
                <dd className="mt-2 text-small text-muted">{item.description}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {latestObservations.length > 0 && (
        <section className="border-b border-border">
          <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
            <SectionHeading
              eyebrow="Latest observations"
              title="Recent captures across the network"
              description="One current observation from each station, newest first."
              action={{ label: "Browse all observations", href: "/observations" }}
            />
            <ul className="mt-6 divide-y divide-border">
              {latestObservations.map((item) => {
                const station = stationById.get(item.stationId);
                const camera = cameraById.get(item.cameraId);
                return (
                  <li key={item.id}>
                    <Link
                      href={`/stations/${item.stationId}/archive/${item.id}`}
                      className="flex items-center gap-4 py-4"
                    >
                      <ObservationThumbnail item={item} sizes="80px" aspectClassName="h-16 w-20 shrink-0" />
                      <span className="min-w-0">
                        <span className="block text-small font-medium text-foreground">
                          {station?.name ?? item.stationId}
                        </span>
                        <span className="mt-1 block text-meta uppercase tracking-label text-muted">
                          {camera?.name ?? item.cameraId} &middot; {formatMediaTypeLabel(item.mediaType)}{" "}
                          &middot; {formatLocalDateTime(item.capturedAtUtc, item.displayTimeZone)}
                        </span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      )}

      <section>
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 sm:py-20 lg:grid-cols-[2fr_3fr] lg:gap-16">
          <h2 className="font-display text-heading-lg text-foreground">
            From camera frames to long-term coastal records
          </h2>
          <div className="space-y-4 text-body text-muted">
            <p>
              A single frame from a fixed camera shows conditions on one day. The same station,
              camera and view direction repeated over months and years shows how a beach, dune or
              headland is actually changing.
            </p>
            <p>
              AusCIN catalogues imagery from fixed reference cameras, lidar stations, existing
              infrastructure and CoastSnap observations against a shared station and camera
              record. The same structure is built to connect that imagery to the coastal datasets
              and research products it supports, so a capture is never just a picture on its own.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
