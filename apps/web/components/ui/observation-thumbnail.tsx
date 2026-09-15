import Image from "next/image";
import type { MediaItem } from "@/data";
import { cn } from "@/lib/cn";
import { getObservationBadge } from "@/lib/observation-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusLabel } from "@/components/ui/status-label";

type ObservationThumbnailProps = {
  item: MediaItem;
  sizes: string;
  /** Tailwind aspect-ratio utility class. Defaults to the gallery-card ratio. */
  aspectClassName?: string;
};

/**
 * A thumbnail with graceful fallbacks for the states real observations
 * can be in: still processing (skeleton), failed or otherwise missing a
 * thumbnail (a plain "Unavailable" placeholder), or flagged by a status
 * badge (processing, failed, or a non-public publication status).
 * Always renders thumbnailUrl, never a preview or original file.
 */
export function ObservationThumbnail({
  item,
  sizes,
  aspectClassName = "aspect-[4/3]",
}: ObservationThumbnailProps) {
  const badge = getObservationBadge(item);

  return (
    <div className={cn("relative overflow-hidden bg-border/40", aspectClassName)}>
      {item.thumbnailUrl ? (
        <Image src={item.thumbnailUrl} alt={item.altText} fill sizes={sizes} className="object-cover" />
      ) : item.processingStatus === "processing" ? (
        <Skeleton className="absolute inset-0" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center px-2 text-center text-meta uppercase tracking-label text-muted">
          Unavailable
        </div>
      )}
      {badge && (
        <span className="absolute left-2 top-2 bg-surface/90 px-2 py-1">
          <StatusLabel label={badge.label} tone={badge.tone} />
        </span>
      )}
    </div>
  );
}
