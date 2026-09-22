import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { MetadataList } from "@/components/ui/metadata-list";
import { StatusLabel } from "@/components/ui/status-label";
import { coastSnapRepository } from "@/data";
import { formatCoordinates, formatLocalDate, formatOperationalDate } from "@/lib/format";
import { getOperatingStatusTone } from "@/lib/status-tone";

export async function generateMetadata({
  params,
}: PageProps<"/coastsnap/[siteId]">): Promise<Metadata> {
  const { siteId } = await params;
  const site = await coastSnapRepository.getSite(siteId);
  return { title: site ? site.name : "CoastSnap site not found" };
}

export default async function CoastSnapSiteDetailPage({
  params,
}: PageProps<"/coastsnap/[siteId]">) {
  const { siteId } = await params;
  const site = await coastSnapRepository.getSite(siteId);

  if (!site) {
    notFound();
  }

  const [observations, dateRange] = await Promise.all([
    coastSnapRepository.listObservationsForSite(site.id),
    coastSnapRepository.getObservationDateRange(site.id),
  ]);

  const siteMetadata = [
    { label: "Site ID", value: site.id },
    { label: "Coordinates", value: formatCoordinates(site.latitude, site.longitude) },
    { label: "Region", value: site.region },
    { label: "State/territory", value: site.state },
    { label: "Established", value: formatOperationalDate(site.establishedSince) },
    { label: "Source", value: "CoastSnap (Spotteron)" },
    {
      label: "Observation date range",
      value: dateRange
        ? `${formatLocalDate(dateRange.earliest.capturedAtUtc, dateRange.earliest.displayTimeZone)} – ${formatLocalDate(dateRange.latest.capturedAtUtc, dateRange.latest.displayTimeZone)}`
        : "No observations recorded yet",
    },
    { label: "Observations", value: String(observations.length) },
  ];

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <Link href="/coastsnap" className="text-small font-medium text-accent hover:text-accent-strong">
        <span aria-hidden="true">&larr;</span> CoastSnap sites
      </Link>

      <div className="mt-6 grid gap-10 lg:grid-cols-[3fr_2fr] lg:items-start">
        <div>
          <p className="text-meta uppercase tracking-label text-accent">{site.region}</p>
          <h1 className="mt-2 font-display text-display-md text-foreground">{site.name}</h1>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <StatusLabel label={site.status} tone={getOperatingStatusTone(site.status)} />
            <span className="text-meta uppercase tracking-label text-muted">
              Site ID &middot; {site.id}
            </span>
          </div>
          <p className="mt-2 text-meta text-muted">
            Sample development record &mdash; not an operational AusCIN feed.
          </p>

          <p className="mt-6 max-w-xl text-body text-muted">
            {observations.length === 0
              ? `${site.description} No observations have been recorded for this site yet.`
              : `${site.description} Its ${observations.length} observation${
                  observations.length === 1 ? "" : "s"
                } in the sample dataset ${
                  observations.length === 1 ? "comes" : "come"
                } from the CoastSnap community, not from a fixed AusCIN camera.`}
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button href={`/coastsnap/${site.id}/archive`}>
              Browse site archive
              <span aria-hidden="true">&rarr;</span>
            </Button>
          </div>
        </div>

        <div>
          {site.representativeImageUrl ? (
            <div className="relative aspect-video overflow-hidden bg-border/40">
              <Image
                src={site.representativeImageUrl}
                alt={`Representative sample image for ${site.name}, a CoastSnap community photo-monitoring point in ${site.region}`}
                fill
                sizes="(min-width: 1024px) 40vw, 100vw"
                className="object-cover"
              />
            </div>
          ) : (
            <div className="flex aspect-video items-center justify-center border border-dashed border-border text-small text-muted">
              Image unavailable
            </div>
          )}
        </div>
      </div>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Site record</h2>
        <div className="mt-6 max-w-xl">
          <MetadataList items={siteMetadata} />
        </div>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-md text-foreground">Data access</h2>
        <p className="mt-3 max-w-xl text-small text-muted">
          Original CoastSnap photo downloads are not available in this prototype &mdash; every
          observation shown here is a synthetic development fixture with no real original file to
          serve. Once real observations are ingested from Spotteron, downloads here are intended
          to follow the same publication-status rules already used across the rest of the
          archive: public, embargoed, project-only or restricted.
        </p>
      </section>
    </div>
  );
}
