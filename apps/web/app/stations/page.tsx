import type { Metadata } from "next";
import { ImageCard } from "@/components/ui/image-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { getAllStations, getCamerasForStation, getMediaForStation } from "@/data";

export const metadata: Metadata = {
  title: "Stations",
};

/**
 * Minimal data-preview page: confirms the sample station/camera/media
 * data loads and can drive the existing design-system components. Not
 * the final station archive or detail page — those are separate tasks.
 */
export default function StationsPage() {
  const stations = getAllStations();

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
          These six stations are sample development records, not an operational AusCIN feed —
          useful for testing station, camera and media data before real observation sites are
          connected.
        </p>
      </div>
      <div className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
        {stations.map((station) => {
          const cameraCount = getCamerasForStation(station.id).length;
          const mediaCount = getMediaForStation(station.id).length;
          return (
            <ImageCard
              key={station.id}
              href={`/stations/${station.id}`}
              src={station.representativeImageUrl}
              alt={`Representative sample image for ${station.name}`}
              title={station.name}
              meta={`${station.region} · ${cameraCount} cameras · ${mediaCount} observations`}
              status={{
                label: station.operationalStatus,
                tone: station.operationalStatus === "active" ? "positive" : "caution",
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
