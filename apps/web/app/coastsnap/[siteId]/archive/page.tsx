import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ObservationThumbnail } from "@/components/ui/observation-thumbnail";
import { coastSnapRepository } from "@/data";
import { formatLocalDateTime } from "@/lib/format";
import { formatMediaTypeLabel } from "@/lib/observation-badge";
import {
  buildArchiveHref,
  countActiveFilters,
  filtersToParamState,
  hasActiveFilters,
  MEDIA_TYPES,
  PAGE_SIZE,
  parseCoastSnapArchiveFilters,
  summariseFilters,
  type SearchParams,
} from "./filters";

const controlClassName =
  "w-full rounded-sm border border-border bg-surface px-3 py-2 text-small text-foreground";
const labelClassName = "flex flex-col gap-1 text-small text-foreground";

export async function generateMetadata({
  params,
}: PageProps<"/coastsnap/[siteId]/archive">): Promise<Metadata> {
  const { siteId } = await params;
  const site = await coastSnapRepository.getSite(siteId);
  return { title: site ? `${site.name} archive` : "CoastSnap site not found" };
}

export default async function CoastSnapSiteArchivePage({
  params,
  searchParams,
}: PageProps<"/coastsnap/[siteId]/archive">) {
  const { siteId } = await params;
  const search: SearchParams = await searchParams;
  const site = await coastSnapRepository.getSite(siteId);

  if (!site) {
    notFound();
  }

  const filters = parseCoastSnapArchiveFilters(search);
  const activeFilters = hasActiveFilters(filters);
  const activeFilterCount = countActiveFilters(filters);
  const paramState = filtersToParamState(filters);
  const summaryParts = summariseFilters(filters);

  const {
    items: pageItems,
    total: totalCount,
    page,
    pageSize,
    totalPages,
  } = await coastSnapRepository.listObservationsForSitePaginated(site.id, filters, {
    page: filters.page,
    pageSize: PAGE_SIZE,
  });
  const rangeStart = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min((page - 1) * pageSize + pageSize, totalCount);

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <Link
        href={`/coastsnap/${site.id}`}
        className="text-small font-medium text-accent hover:text-accent-strong"
      >
        <span aria-hidden="true">&larr;</span> {site.name}
      </Link>

      <p className="mt-6 text-meta uppercase tracking-label text-accent">CoastSnap archive</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">
        Community photos at {site.name}
      </h1>
      <p className="mt-1 text-meta uppercase tracking-label text-muted">
        {site.region} &middot; Site ID {site.id}
      </p>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed. Every photo below is a
        synthetic fixture and every contributor credit is invented for interface testing.
      </p>

      <details className="mt-10 border-t border-b border-border" open={activeFilters}>
        <summary className="cursor-pointer select-none py-4 text-small font-medium text-foreground">
          Filters{activeFilterCount > 0 ? ` (${activeFilterCount} active)` : ""}
        </summary>
        <form method="get" action={`/coastsnap/${site.id}/archive`} className="pb-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <label className={labelClassName}>
              Media type
              <select name="mediaType" defaultValue={filters.mediaType ?? ""} className={controlClassName}>
                <option value="">All types</option>
                {MEDIA_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {formatMediaTypeLabel(type)}
                  </option>
                ))}
              </select>
            </label>

            <label className={labelClassName}>
              From date
              <input type="date" name="from" defaultValue={filters.from ?? ""} className={controlClassName} />
            </label>

            <label className={labelClassName}>
              To date
              <input type="date" name="to" defaultValue={filters.to ?? ""} className={controlClassName} />
            </label>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button type="submit">Apply filters</Button>
            {activeFilters && (
              <Link
                href={`/coastsnap/${site.id}/archive`}
                className="text-small font-medium text-accent hover:text-accent-strong"
              >
                Clear filters
              </Link>
            )}
          </div>
        </form>
      </details>

      <div className="mt-6 border-b border-border pb-6">
        <p className="text-small text-foreground">
          <span className="font-medium">{totalCount}</span> observation{totalCount === 1 ? "" : "s"}
          {summaryParts.length > 0 && <> &middot; {summaryParts.join(" · ")}</>}
          {totalCount > 0 && (
            <>
              {" "}
              &middot; showing {rangeStart}&ndash;{rangeEnd}
            </>
          )}
        </p>
        <p className="mt-2 max-w-2xl text-meta text-muted">
          Date filters match each observation&apos;s own local calendar day at {site.name}, not a
          shared UTC window.
        </p>
      </div>

      {pageItems.length === 0 ? (
        <EmptyState
          className="mt-10"
          title={activeFilters ? "No observations match these filters" : "No observations yet"}
          description={
            activeFilters
              ? "Try a different media type or date range, or clear the filters to see this site's whole record."
              : "This site has no CoastSnap contributions in the sample dataset yet."
          }
          action={
            activeFilters ? { label: "Clear filters", href: `/coastsnap/${site.id}/archive` } : undefined
          }
        />
      ) : (
        <>
          <div className="mt-10 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
            {pageItems.map((item) => (
              <Link
                key={item.id}
                href={`/coastsnap/${site.id}/archive/${item.id}`}
                className="block border-t border-border pt-3"
              >
                <ObservationThumbnail item={item} sizes="(min-width: 1024px) 25vw, 50vw" />
                <p className="mt-2 text-small font-medium text-foreground">
                  {formatMediaTypeLabel(item.mediaType)}
                </p>
                <p className="mt-1 text-meta uppercase tracking-label text-muted">
                  {formatLocalDateTime(item.capturedAtUtc, item.displayTimeZone)}
                </p>
                <p className="mt-1 text-meta uppercase tracking-label text-muted">
                  {item.contributor.attributionText} &middot; {item.contributor.displayName}
                </p>
                <p className="mt-1 text-small text-muted">{item.caption}</p>
              </Link>
            ))}
          </div>

          <div className="mt-10 flex items-center justify-between border-t border-border pt-6">
            {page > 1 ? (
              <Link
                href={buildArchiveHref(site.id, { ...paramState, page: String(page - 1) })}
                className="text-small font-medium text-accent hover:text-accent-strong"
              >
                &larr; Previous
              </Link>
            ) : (
              <span className="text-small text-muted" aria-disabled="true">
                &larr; Previous
              </span>
            )}
            <p className="text-meta uppercase tracking-label text-muted">
              Page {page} of {totalPages}
            </p>
            {page < totalPages ? (
              <Link
                href={buildArchiveHref(site.id, { ...paramState, page: String(page + 1) })}
                className="text-small font-medium text-accent hover:text-accent-strong"
              >
                Next &rarr;
              </Link>
            ) : (
              <span className="text-small text-muted" aria-disabled="true">
                Next &rarr;
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
