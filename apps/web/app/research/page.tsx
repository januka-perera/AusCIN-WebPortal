import type { Metadata } from "next";
import Link from "next/link";
import { StatusLabel } from "@/components/ui/status-label";
import type { ProcessingStatus, PublicationStatus } from "@/data";
import { formatPublicationLabel } from "@/lib/observation-badge";
import { getProcessingStatusTone, getPublicationStatusTone } from "@/lib/status-tone";

export const metadata: Metadata = {
  title: "Research",
};

const RECORD_FIELDS = [
  { label: "Station", description: "Which station captured the observation, with its state or territory and region." },
  { label: "Camera", description: "The specific camera at that station, including its view direction and type." },
  { label: "Capture time (UTC)", description: "The capture instant stored in UTC, so records from different time zones stay directly comparable." },
  { label: "Local time zone", description: "The IANA time zone used to display the capture time to a visitor at that station's location." },
  { label: "Media type", description: "Image, composite or time-lapse video." },
  { label: "Dimensions", description: "Pixel width and height of the capture." },
  { label: "Duration", description: "Recorded only for time-lapse media, in seconds." },
  { label: "Processing status", description: "Where the capture is in the processing pipeline: processed, processing or failed." },
  { label: "Publication status", description: "Who the record is visible to: public, embargoed, project-only or restricted." },
  { label: "Related media", description: "Other captures — from the same event, camera or nearby moment — linked to this record." },
  { label: "Provenance", description: "The capture's station, camera and processing history, kept attached where available." },
];

const PROCESSING_STATES: { status: ProcessingStatus; description: string }[] = [
  { status: "processed", description: "The capture has completed processing and has a thumbnail and preview ready to browse." },
  { status: "processing", description: "The capture is still moving through the processing pipeline; no preview is available yet." },
  { status: "failed", description: "Processing could not complete for this capture; no preview will be generated." },
];

const PUBLICATION_STATES: { status: PublicationStatus; description: string }[] = [
  { status: "public", description: "Visible to any visitor, subject to its processing status." },
  { status: "embargoed", description: "Held back from general access for a defined period before publication." },
  { status: "project-only", description: "Limited to a specific research project or collaboration." },
  { status: "restricted", description: "Not available for general or download access." },
];

export default function ResearchPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">Research and data access</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">
        Research and data products
      </h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed.
      </p>

      <p className="mt-6 max-w-2xl text-body text-muted">
        The imagery catalogue is intended to connect individual observations with the coastal
        datasets and analysis-ready products they support &mdash; so a capture is a reference
        point in a larger record, not just a picture on its own. This page describes what an
        observation record is intended to contain, how access is controlled, and how to use the
        archive that is implemented in this prototype today.
      </p>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">
          What an observation record contains
        </h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          Every media record in the catalogue carries the same set of fields, regardless of which
          station or camera produced it:
        </p>
        <dl className="mt-8 divide-y divide-border border-t border-border">
          {RECORD_FIELDS.map((field) => (
            <div key={field.label} className="py-3">
              <dt className="text-small font-medium text-foreground">{field.label}</dt>
              <dd className="mt-1 max-w-xl text-small text-muted">{field.description}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Media and processing states</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          Processing status and publication status are independent: a record can be fully
          processed and still not publicly visible, or public once it clears an embargo.
        </p>

        <div className="mt-8 grid gap-10 sm:grid-cols-2">
          <div>
            <h3 className="text-meta uppercase tracking-label text-muted">Processing status</h3>
            <ul className="mt-4 space-y-4">
              {PROCESSING_STATES.map((item) => (
                <li key={item.status} className="flex flex-col gap-1">
                  <StatusLabel label={item.status} tone={getProcessingStatusTone(item.status)} />
                  <p className="text-small text-muted">{item.description}</p>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-meta uppercase tracking-label text-muted">Publication status</h3>
            <ul className="mt-4 space-y-4">
              {PUBLICATION_STATES.map((item) => (
                <li key={item.status} className="flex flex-col gap-1">
                  <StatusLabel
                    label={formatPublicationLabel(item.status)}
                    tone={getPublicationStatusTone(item.status)}
                  />
                  <p className="text-small text-muted">{item.description}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Using the archive</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          Observations can be filtered by station, camera, date range, time of day and media type,
          with the current search state kept in the URL so a filtered view can be bookmarked or
          shared. Three entry points cover different ways of finding a record:
        </p>
        <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2">
          <Link href="/stations" className="text-small font-medium text-accent hover:text-accent-strong">
            Browse stations &rarr;
          </Link>
          <Link href="/observations" className="text-small font-medium text-accent hover:text-accent-strong">
            Search observations &rarr;
          </Link>
          <Link href="/map" className="text-small font-medium text-accent hover:text-accent-strong">
            View the network map &rarr;
          </Link>
        </div>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Downloads and access</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          Where a record&apos;s publication status permits it, an observation&apos;s detail page
          offers a download of the original file; restricted records show that access is not
          permitted instead. This development prototype does not yet serve original files for any
          record, so downloads are not available here regardless of publication status.
        </p>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Related products</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          AusCIN&apos;s catalogue is intended to link an observation or station to the coastal
          datasets and research products its imagery supports. That linking is not implemented in
          this prototype, and no such datasets or products are listed here yet.
        </p>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Prototype status</h2>
        <p className="mt-4 max-w-2xl text-body text-muted">
          Every record referenced on this page &mdash; station, camera, capture and metadata
          field &mdash; is a synthetic development fixture, used to build and test this interface.
          None of it reflects a real AusCIN research product or an operational data service.
        </p>
      </section>
    </div>
  );
}
