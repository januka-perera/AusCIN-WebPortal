import type { Metadata } from "next";
import Link from "next/link";
import { repository } from "@/data";

export const metadata: Metadata = {
  title: "About",
};

const OBSERVATION_SOURCES = [
  {
    name: "Fixed coastal cameras",
    description:
      "A camera mounted at a stable position and view direction, capturing images at a set interval so the same framing can be compared day to day and season to season.",
  },
  {
    name: "Lidar reference stations",
    description:
      "A subset of stations extend a fixed camera with a lidar scanner, adding measured elevation and profile data alongside imagery from the same location.",
  },
  {
    name: "Cameras of opportunity",
    description:
      "Existing camera infrastructure not originally installed for coastal monitoring — surf, harbour or public webcams — brought into the catalogue where their view and access terms make them useful.",
  },
  {
    name: "CoastSnap observations",
    description:
      "Public phone photographs taken from a fixed cradle or alignment mark, extending station-style coverage to community-monitored locations between formally instrumented sites.",
  },
];

const CATALOGUE_STAGES = [
  {
    stage: "Capture",
    description: "A camera or scanner records an image, composite or time-lapse at a known time.",
  },
  {
    stage: "Station and camera metadata",
    description:
      "The capture is tied to its station, camera, coordinates and view direction, so it stays comparable with other captures from the same or different sites.",
  },
  {
    stage: "Processing",
    description:
      "The original capture is processed before publication; a record can be processed, still processing, or failed if that step could not complete.",
  },
  {
    stage: "Thumbnails and previews",
    description:
      "Browser-sized thumbnails and previews are generated for galleries and detail pages, keeping the archive fast without loading full-resolution originals.",
  },
  {
    stage: "Publication status",
    description:
      "Each record carries a publication status — public, embargoed, project-only or restricted — independent of whether it has finished processing.",
  },
  {
    stage: "Permitted access",
    description:
      "Original-file downloads are offered only where publication status allows it, rather than being tied to whether a file happens to exist.",
  },
  {
    stage: "Related data products",
    description:
      "A station or capture is intended to link onward to the coastal datasets and research products its imagery supports.",
  },
];

export default async function AboutPage() {
  const stations = await repository.listStations();
  const stationNames = stations.map((station) => station.name).join(", ");

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">Coastal observation network</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">About AusCIN</h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed.
      </p>

      <p className="mt-6 max-w-2xl text-body text-muted">
        AusCIN &mdash; the Australian Coastline Imaging Network &mdash; is a coordinated way of
        collecting and cataloguing coastal observations from stations placed along different parts
        of the Australian coast. A single camera or scanner at one station only shows one place at
        one moment; AusCIN&apos;s purpose is to bring many stations&apos; cameras, timestamps and
        metadata into one consistent structure so they can be searched, compared and referenced
        together, rather than sitting as separate, disconnected feeds.
      </p>
      <p className="mt-4 max-w-2xl text-body text-muted">
        This portal is intended for three audiences: researchers studying coastal processes,
        coastal managers monitoring change and planning responses, and members of the public
        interested in their local coastline.
      </p>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">
          A shared record of coastal observations
        </h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          A single frame from a fixed camera shows conditions on one day. The same station, camera
          and view direction repeated over months and years shows how a beach, dune or headland is
          actually changing &mdash; storm erosion and recovery, dune vegetation cover, sandbar
          movement, or how a coastline responds after a specific weather event. That kind of
          comparison only works if every capture keeps consistent metadata: which station, which
          camera, what time, and what has happened to the file since it was captured.
        </p>
        <p className="mt-4 max-w-2xl text-body text-muted">
          A coordinated catalogue also lets a search follow coastal change across the network,
          rather than requiring a separate visit to each station&apos;s own records.
        </p>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Observation sources</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          AusCIN is designed to bring together four kinds of observation source. Not every source
          is already connected in a given deployment &mdash; a station record states which
          cameras it actually has.
        </p>
        <dl className="mt-8 divide-y divide-border border-t border-border">
          {OBSERVATION_SOURCES.map((source) => (
            <div key={source.name} className="py-5">
              <dt className="font-display text-heading-md text-foreground">{source.name}</dt>
              <dd className="mt-2 max-w-2xl text-small text-muted">{source.description}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">From capture to catalogue</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          Every observation is intended to move through the same stages, so a researcher or
          coastal manager can trust that a record from one station means the same thing as a
          record from another.
        </p>
        <ol className="mt-8 divide-y divide-border border-t border-border">
          {CATALOGUE_STAGES.map((item, index) => (
            <li key={item.stage} className="flex gap-4 py-4">
              <span className="text-meta uppercase tracking-label text-muted">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="text-small font-medium text-foreground">{item.stage}</p>
                <p className="mt-1 max-w-xl text-small text-muted">{item.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Development status</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          This interface is a frontend-only development prototype. Every station, camera and
          observation record it shows &mdash; {stationNames} &mdash; is a synthetic fixture
          generated for interface development and testing. Their coordinates, cameras, capture
          history and imagery are not real coastal monitoring installations, and none of it comes
          from an operational AusCIN feed.
        </p>
        <p className="mt-4 max-w-2xl text-body text-muted">
          The thumbnails, previews and poster frames used throughout this prototype are local
          placeholder images, not photographs of real coastal sites. A future operational service
          would connect this same station/camera/media structure to real capture hardware,
          processing pipelines and publication controls.
        </p>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Data principles</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          Beyond this prototype, AusCIN&apos;s catalogue is intended to work toward:
        </p>
        <ul className="mt-6 max-w-2xl space-y-3 text-body text-muted">
          <li>
            <span className="font-medium text-foreground">Consistent metadata</span> &mdash; the
            same station, camera, timestamp and status fields on every record, regardless of
            observation source.
          </li>
          <li>
            <span className="font-medium text-foreground">Discoverability</span> &mdash; records
            that can be found by station, camera, date, time and media type rather than only by
            browsing a single site&apos;s files.
          </li>
          <li>
            <span className="font-medium text-foreground">Accessible publication pathways</span>{" "}
            &mdash; a clear publication status on every record, so access decisions are explicit
            rather than dependent on where a file happens to sit.
          </li>
          <li>
            <span className="font-medium text-foreground">Interoperability and reuse</span> &mdash;
            a structure that can connect to related coastal datasets and research products instead
            of standing alone.
          </li>
          <li>
            <span className="font-medium text-foreground">Provenance</span> &mdash; keeping each
            record&apos;s station, camera and processing history attached to it, not just its
            image.
          </li>
        </ul>
        <p className="mt-6 max-w-2xl text-small text-muted">
          Working toward findable, accessible, interoperable and reusable (FAIR) data practices is
          a longer-term goal for AusCIN, not a compliance claim about this prototype.
        </p>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-md text-foreground">Explore the archive</h2>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
          <Link href="/stations" className="text-small font-medium text-accent hover:text-accent-strong">
            Browse stations &rarr;
          </Link>
          <Link href="/observations" className="text-small font-medium text-accent hover:text-accent-strong">
            Search observations &rarr;
          </Link>
          <Link href="/map" className="text-small font-medium text-accent hover:text-accent-strong">
            View the network map &rarr;
          </Link>
          <Link href="/research" className="text-small font-medium text-accent hover:text-accent-strong">
            Research and data access &rarr;
          </Link>
        </div>
      </section>
    </div>
  );
}
