import type { Metadata } from "next";
import { ImageCard } from "@/components/ui/image-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { repository } from "@/data";
import { getOperatingStatusTone } from "@/lib/status-tone";

export const metadata: Metadata = {
  title: "Stations",
};

export default async function StationsPage() {
  const stations = await repository.listStations();
  const stationSummaries = await Promise.all(
    stations.map(async (station) => ({
      station,
      cameraCount: (await repository.listCamerasForStation(station.id)).length,
      mediaCount: (await repository.listStationObservations(station.id, {})).length,
    })),
  );

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <SectionHeading
        level="h1"
        eyebrow="Stations"
        title="Station records"
        description="Fixed cameras and lidar scanners grouped by station, each with a stable location, view direction and operating status."
      />
      <div className="mt-6 max-w-2xl space-y-4 text-body text-muted">
        <p>
          Each station accumulates its own archive of images, composites and time-lapse video.
          Every capture keeps its camera, timestamp in UTC, displayed local time zone and
          processing status, so records stay comparable across stations in different Australian
          states and time zones.
        </p>
        <p>
          These {stations.length} stations are sample development records, not an operational
          AusCIN feed — useful for testing station, camera and media data before real observation
          sites are connected.
        </p>
      </div>
      <div className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
        {stationSummaries.map(({ station, cameraCount, mediaCount }) => (
          <ImageCard
            key={station.id}
            href={`/stations/${station.id}`}
            src={station.representativeImageUrl}
            alt={`Representative sample image for ${station.name}`}
            title={station.name}
            meta={`${station.region} · ${cameraCount} camera${cameraCount === 1 ? "" : "s"} · ${mediaCount} observation${mediaCount === 1 ? "" : "s"}`}
            status={{
              label: station.operationalStatus,
              tone: getOperatingStatusTone(station.operationalStatus),
            }}
          />
        ))}
      </div>
    </div>
  );
}
