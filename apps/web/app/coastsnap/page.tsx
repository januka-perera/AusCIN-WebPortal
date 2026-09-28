import type { Metadata } from "next";
import { connection } from "next/server";
import { EmptyState } from "@/components/ui/empty-state";
import { ImageCard } from "@/components/ui/image-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { coastSnapRepository, getCoastSnapDataSource } from "@/data";
import { getRecordNotice } from "@/lib/coastsnap-presentation";
import { formatApproximateLocation } from "@/lib/format";
import { getOperatingStatusTone } from "@/lib/status-tone";

export const metadata: Metadata = {
  title: "CoastSnap",
};

/** How many recent observations to look through for a stand-in site image. */
const RECENT_WINDOW = 12;

export default async function CoastSnapPage() {
  // Render at request time, so the data source (sample fixtures or the catalogue API)
  // follows the server's runtime COASTSNAP_API_BASE_URL rather than whatever was set
  // during `next build`.
  await connection();
  const source = getCoastSnapDataSource();

  const sites = await coastSnapRepository.listSites();
  const siteSummaries = await Promise.all(
    sites.map(async (site) => {
      // One small page gives both the count and recent observations. The newest one with a
      // thumbnail stands in for sites without a representative image (every API site today).
      const { total, items } = await coastSnapRepository.listObservationsForSitePaginated(
        site.id,
        {},
        { page: 1, pageSize: RECENT_WINDOW },
      );
      const latest = items.find((item) => item.thumbnailUrl);
      return {
        site,
        observationCount: total,
        imageSrc: site.representativeImageUrl ?? latest?.thumbnailUrl ?? null,
        imageAlt: site.representativeImageUrl
          ? `Representative ${site.isSynthetic ? "sample " : ""}image for ${site.name}`
          : latest?.altText ?? `No image available yet for ${site.name}`,
      };
    }),
  );
  const pageNotice = source === "sample" ? getRecordNotice(source, true) : null;
  const hasSyntheticApiSites = source === "api" && sites.some((site) => site.isSynthetic);

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">Community coastal photos</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">CoastSnap</h1>
      {pageNotice && <p className="mt-2 text-meta text-muted">{pageNotice}</p>}

      <p className="mt-6 max-w-2xl text-body text-muted">
        CoastSnap invites members of the public to contribute their own coastal photos, lined up
        against a fixed alignment mark at a monitored site. Unlike AusCIN&apos;s fixed-camera and
        lidar stations, a CoastSnap site has no permanently installed camera or scanner &mdash;
        every observation comes from a visitor&apos;s own phone, which is why each one carries a
        contributor credit instead of a camera ID.
      </p>
      {source === "sample" ? (
        <p className="mt-4 max-w-2xl text-body text-muted">
          This area of the portal is a frontend-only development preview: every site, contributor
          and photo shown here is a synthetic fixture, generated for interface development and
          testing. None of it has come from the real Spotteron platform, and none of these sites
          correspond to a real coastal location.
        </p>
      ) : (
        hasSyntheticApiSites && (
          <p className="mt-4 max-w-2xl text-body text-muted">
            Sites marked &ldquo;Synthetic&rdquo; below are test records served by the development
            catalogue &mdash; not an operational AusCIN feed.
          </p>
        )
      )}

      <section className="mt-16 border-t border-border pt-10">
        <SectionHeading
          title="CoastSnap sites"
          description="Community photo-monitoring points, each with a fixed alignment mark for consistent framing over time."
        />
        {siteSummaries.length === 0 ? (
          <EmptyState
            className="mt-10"
            title="No CoastSnap sites yet"
            description={
              source === "sample"
                ? "No CoastSnap sites are recorded in the sample dataset."
                : "No CoastSnap sites have been published yet."
            }
          />
        ) : (
          <div className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {siteSummaries.map(({ site, observationCount, imageSrc, imageAlt }) => (
              <ImageCard
                key={site.id}
                href={`/coastsnap/${site.id}`}
                src={imageSrc}
                alt={imageAlt}
                title={site.name}
                meta={`${site.region} · ${formatApproximateLocation(site.latitude, site.longitude)} · ${observationCount} observation${observationCount === 1 ? "" : "s"}${source === "api" && site.isSynthetic ? " · Synthetic" : ""}`}
                status={{ label: site.status, tone: getOperatingStatusTone(site.status) }}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
