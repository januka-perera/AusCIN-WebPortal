import type { Metadata } from "next";
import { EmptyState } from "@/components/ui/empty-state";
import { ImageCard } from "@/components/ui/image-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { coastSnapRepository } from "@/data";
import { getOperatingStatusTone } from "@/lib/status-tone";

export const metadata: Metadata = {
  title: "CoastSnap",
};

export default async function CoastSnapPage() {
  const sites = await coastSnapRepository.listSites();
  const siteSummaries = await Promise.all(
    sites.map(async (site) => ({
      site,
      observationCount: (await coastSnapRepository.listObservationsForSite(site.id)).length,
    })),
  );

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">Community coastal photos</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">CoastSnap</h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed.
      </p>

      <p className="mt-6 max-w-2xl text-body text-muted">
        CoastSnap invites members of the public to contribute their own coastal photos, lined up
        against a fixed alignment mark at a monitored site, extending AusCIN&apos;s station
        coverage to community-monitored locations. This area of the portal is a frontend-only
        development preview: every site, contributor and photo shown here is a synthetic fixture,
        generated for interface development and testing. None of it has come from the real
        Spotteron platform, and none of these sites correspond to a real coastal location.
      </p>

      <section className="mt-16 border-t border-border pt-10">
        <SectionHeading
          title="CoastSnap sites"
          description="Community photo-monitoring points, each with a fixed alignment mark for consistent framing over time."
        />
        {siteSummaries.length === 0 ? (
          <EmptyState
            className="mt-10"
            title="No CoastSnap sites yet"
            description="No CoastSnap sites are recorded in the sample dataset."
          />
        ) : (
          <div className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {siteSummaries.map(({ site, observationCount }) => (
              <ImageCard
                key={site.id}
                src={site.representativeImageUrl}
                alt={`Representative sample image for ${site.name}`}
                title={site.name}
                meta={`${site.region} · ${observationCount} observation${observationCount === 1 ? "" : "s"}`}
                status={{ label: site.status, tone: getOperatingStatusTone(site.status) }}
              />
            ))}
          </div>
        )}
        <p className="mt-6 max-w-2xl text-small text-muted">
          Individual site pages, photo archives and detail pages are part of a later development
          stage and are not yet linked from here.
        </p>
      </section>
    </div>
  );
}
