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
        eyebrow="Stations"
        title="Coastal cameras across Australia"
        description="Sample stations from the local development dataset, used to verify station, camera and media data loads correctly."
      />
      <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
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
