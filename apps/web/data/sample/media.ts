import type { MediaItem, MediaType, PublicationStatus, Station } from "../types/media";
import { CAMERAS } from "./cameras";
import { STATIONS } from "./stations";

/**
 * Synthetic media fixtures for local development.
 *
 * The bulk of the dataset is produced deterministically by looping over
 * every camera and a small fixed set of sample dates/times (no random
 * values, so the fixture is stable across runs). A handful of specific
 * records are then adjusted in place to cover the edge cases the
 * interface needs to handle: items still processing, a missing preview,
 * a failed capture, an offline camera, a camera and station with no
 * observations at all, a day skipped for one camera, embargoed and
 * restricted records independent of processing status, a time-lapse
 * tied to several images, and same-local-time-different-UTC
 * observations from stations in different time zones.
 */

type SlotType = "morning" | "midday" | "afternoon" | "sunset" | "night";

type Slot = {
  type: SlotType;
  /** Local (station time zone) time of day, 24h "HH:MM". */
  localTime: string;
  label: string;
};

const SLOTS: Slot[] = [
  { type: "morning", localTime: "06:00", label: "Morning" },
  { type: "midday", localTime: "12:00", label: "Midday" },
  { type: "afternoon", localTime: "15:30", label: "Afternoon" },
  { type: "sunset", localTime: "19:00", label: "Sunset" },
  { type: "night", localTime: "22:00", label: "Night" },
];

/** Three consecutive local dates, enough to exercise date-range filtering. */
const SAMPLE_DATES = ["2025-02-10", "2025-02-11", "2025-02-12"];

/** IANA time zone used to display each station's capture times. */
const STATION_TIME_ZONE: Record<string, string> = {
  "STN-SEAGLASS": "Australia/Sydney",
  "STN-KESTREL": "Australia/Melbourne",
  "STN-WINDARA": "Australia/Adelaide",
  "STN-MIRRIGAN": "Australia/Perth",
  "STN-TALWARRA": "Australia/Brisbane",
  "STN-BLUEWATER": "Australia/Hobart",
  "STN-PELICAN": "Australia/Darwin",
};

/**
 * Fixed UTC offset (hours) for each time zone above, valid for the
 * SAMPLE_DATES window only (southern-hemisphere summer: NSW/VIC/TAS/SA
 * observe daylight saving, QLD/WA do not). This is a small hand-authored
 * lookup for fixture generation, not a general time zone library.
 */
const UTC_OFFSET_HOURS: Record<string, number> = {
  "Australia/Sydney": 11,
  "Australia/Melbourne": 11,
  "Australia/Hobart": 11,
  "Australia/Adelaide": 10.5,
  "Australia/Perth": 8,
  "Australia/Brisbane": 10,
  "Australia/Darwin": 9.5,
};

function toUtcIso(localDate: string, localTime: string, timeZone: string): string {
  const offsetHours = UTC_OFFSET_HOURS[timeZone];
  const [year, month, day] = localDate.split("-").map(Number);
  const [hour, minute] = localTime.split(":").map(Number);
  const utcMinutes = hour * 60 + minute - Math.round(offsetHours * 60);
  return new Date(Date.UTC(year, month - 1, day, 0, utcMinutes)).toISOString();
}

type SceneKey =
  | "beach-wide"
  | "headland-rocky"
  | "water-calm"
  | "water-high-swell"
  | "sunset"
  | "night-low-light"
  | "lidar-composite";

const SCENE_FILE: Record<SceneKey, string> = {
  "beach-wide": "beach-wide.svg",
  "headland-rocky": "headland-rocky.svg",
  "water-calm": "water-calm.svg",
  "water-high-swell": "water-high-swell.svg",
  sunset: "sunset.svg",
  "night-low-light": "night-low-light.svg",
  "lidar-composite": "lidar-composite.svg",
};

const SCENE_LABEL: Record<SceneKey, string> = {
  "beach-wide": "wide beach",
  "headland-rocky": "rocky headland",
  "water-calm": "calm water",
  "water-high-swell": "high swell",
  sunset: "sunset",
  "night-low-light": "low-light",
  "lidar-composite": "lidar composite",
};

const SLOT_SCENE: Record<SlotType, SceneKey> = {
  morning: "beach-wide",
  midday: "water-calm",
  afternoon: "water-high-swell",
  sunset: "sunset",
  night: "night-low-light",
};

const TIMELAPSE_POSTER_URL = "/sample-media/posters/timelapse-poster.svg";

function thumbnailUrl(scene: SceneKey): string {
  return `/sample-media/thumbnails/${SCENE_FILE[scene]}`;
}

function previewUrl(scene: SceneKey): string {
  return `/sample-media/previews/${SCENE_FILE[scene]}`;
}

/** Dates to skip entirely for specific cameras, keyed by camera ID. */
const SKIP_DATES: Record<string, string[]> = {
  // Edge case: one day with no observations for this camera.
  "STN-WINDARA-CAM1": ["2025-02-11"],
  // Edge case: this camera is offline (see cameras.ts) and stopped
  // reporting before the last sample date.
  "STN-KESTREL-CAM2": ["2025-02-12"],
  // Edge case: a newly commissioned camera (and, since it is Pelican
  // Reach's only camera, station) with no observations at all yet.
  "STN-PELICAN-CAM1": [...SAMPLE_DATES],
};

const STATION_BY_ID: Record<string, Station> = Object.fromEntries(
  STATIONS.map((station) => [station.id, station]),
);

function dateStamp(date: string): string {
  return date.replace(/-/g, "");
}

function timeStamp(localTime: string): string {
  return localTime.replace(":", "");
}

function buildMedia(): MediaItem[] {
  const media: MediaItem[] = [];

  for (const camera of CAMERAS) {
    const station = STATION_BY_ID[camera.stationId];
    const timeZone = STATION_TIME_ZONE[camera.stationId];
    const isLidar = camera.type === "lidar";
    const skipDates = SKIP_DATES[camera.id] ?? [];

    for (const date of SAMPLE_DATES) {
      if (skipDates.includes(date)) continue;

      const dayMediaIds: string[] = [];

      for (const slot of SLOTS) {
        const scene: SceneKey = isLidar ? "lidar-composite" : SLOT_SCENE[slot.type];
        const mediaType: MediaType = isLidar ? "composite" : "image";
        const id = `${camera.id}-${dateStamp(date)}-${timeStamp(slot.localTime)}`;

        media.push({
          id,
          stationId: camera.stationId,
          cameraId: camera.id,
          mediaType,
          capturedAtUtc: toUtcIso(date, slot.localTime, timeZone),
          displayTimeZone: timeZone,
          width: camera.resolution.width,
          height: camera.resolution.height,
          fileSizeBytes: Math.round(camera.resolution.width * camera.resolution.height * 0.35),
          processingStatus: "processed",
          publicationStatus: isLidar ? "project-only" : "public",
          thumbnailUrl: thumbnailUrl(scene),
          previewUrl: previewUrl(scene),
          originalUrl: null,
          relatedMediaIds: [],
          caption: `${station.name} — ${SCENE_LABEL[scene]} view from ${camera.name}, ${date} ${slot.label.toLowerCase()}`,
          altText: `${SCENE_LABEL[scene]} scene captured by ${camera.name} at ${station.name} on ${date} at ${slot.localTime} local time.`,
        });
        dayMediaIds.push(id);
      }

      if (!isLidar) {
        const timelapseId = `${camera.id}-${dateStamp(date)}-TIMELAPSE`;
        media.push({
          id: timelapseId,
          stationId: camera.stationId,
          cameraId: camera.id,
          mediaType: "timelapse",
          capturedAtUtc: toUtcIso(date, "22:30", timeZone),
          displayTimeZone: timeZone,
          durationSeconds: 30,
          width: camera.resolution.width,
          height: camera.resolution.height,
          fileSizeBytes: 30 * 250_000,
          processingStatus: "processed",
          publicationStatus: "public",
          thumbnailUrl: TIMELAPSE_POSTER_URL,
          previewUrl: TIMELAPSE_POSTER_URL,
          originalUrl: null,
          relatedMediaIds: [...dayMediaIds],
          caption: `${station.name} — daily summary time-lapse for ${date} from ${camera.name}`,
          altText: `Time-lapse compiling ${dayMediaIds.length} images from ${camera.name} at ${station.name} on ${date}.`,
        });

        // Link the day's stills back to the time-lapse that compiles them.
        for (const item of media) {
          if (dayMediaIds.includes(item.id)) {
            item.relatedMediaIds.push(timelapseId);
          }
        }
      }
    }
  }

  return media;
}

export const MEDIA: MediaItem[] = buildMedia();

const byId = new Map(MEDIA.map((item) => [item.id, item]));

function applyOverride(id: string, changes: Partial<MediaItem>): void {
  const item = byId.get(id);
  if (!item) {
    throw new Error(`Sample media override references unknown media ID: ${id}`);
  }
  Object.assign(item, changes);
}

function setPublicationStatus(id: string, status: PublicationStatus): void {
  applyOverride(id, { publicationStatus: status });
}

// Edge case: an extra composite product alongside the usual images, for
// mediaType variety beyond the lidar station.
applyOverride("STN-SEAGLASS-CAM1-20250210-1200", {
  mediaType: "composite",
  caption: "Seaglass Point — stacked high-tide composite from Seaglass Point — North, 2025-02-10 midday",
});
setPublicationStatus("STN-SEAGLASS-CAM1-20250210-1200", "project-only");

// Edge case: item still being processed — nothing to render yet.
applyOverride("STN-TALWARRA-CAM1-20250212-2200", {
  processingStatus: "processing",
  publicationStatus: "embargoed",
  thumbnailUrl: null,
  previewUrl: null,
  caption: "Talwarra Beach — Pier capture from 2025-02-12 night is still processing",
});

// Edge case: processed, but the preview render is unavailable (thumbnail
// still exists).
applyOverride("STN-SEAGLASS-CAM2-20250211-1530", {
  previewUrl: null,
  caption: "Seaglass Point — South capture from 2025-02-11 afternoon (preview unavailable)",
});

// Edge case: capture failed outright — no renderable assets at all.
applyOverride("STN-BLUEWATER-CAM1-20250212-1900", {
  processingStatus: "failed",
  publicationStatus: "restricted",
  thumbnailUrl: null,
  previewUrl: null,
  caption: "Bluewater Spit — North capture from 2025-02-12 sunset failed",
  altText: "Capture failed; no image is available for this observation.",
});

// Edge case: fully processed but embargoed — demonstrates that
// processing status and publication status are independent axes (the
// only other embargoed record above is also still "processing").
setPublicationStatus("STN-KESTREL-CAM1-20250210-1200", "embargoed");

// Edge case: fully processed but restricted — distinct from the failed
// capture above, which is restricted for a different reason.
setPublicationStatus("STN-TALWARRA-CAM2-20250211-1530", "restricted");

/**
 * Edge case: same nominal local time, different UTC instant.
 * Talwarra Beach (QLD, UTC+10, no daylight saving) and Cape Mirrigan
 * (WA, UTC+8, no daylight saving) both record a "06:00" morning
 * observation on 2025-02-10, but two hours apart in UTC:
 *   - STN-TALWARRA-CAM1-20250210-0600 -> 2025-02-09T20:00:00.000Z
 *   - STN-MIRRIGAN-CAM1-20250210-0600 -> 2025-02-09T22:00:00.000Z
 * No override needed here — this falls out of the generator naturally
 * from each station's UTC offset. See data/queries.test.ts.
 */
