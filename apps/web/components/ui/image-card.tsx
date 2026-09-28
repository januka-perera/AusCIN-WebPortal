import Image from "next/image";
import Link from "next/link";
import { StatusLabel, type StatusTone } from "@/components/ui/status-label";
import { isRemoteMediaUrl } from "@/lib/media-url";

type ImageCardProps = {
  /** Omit when the destination page doesn't exist yet — renders a plain, non-interactive card instead of a dead link. */
  href?: string;
  /** Null when no image exists (e.g. an API-backed site with no observations yet) — renders an "Image unavailable" placeholder. */
  src: string | null;
  alt: string;
  title: string;
  meta: string;
  status?: { label: string; tone?: StatusTone };
};

/**
 * A gallery/station card: thumbnail image, title and a metadata line.
 * Always pass a thumbnail path, never an original file, per the
 * media-performance rules in AGENTS.md.
 */
export function ImageCard({ href, src, alt, title, meta, status }: ImageCardProps) {
  const content = (
    <>
      <div className="relative aspect-[4/3] overflow-hidden bg-border/40">
        {src ? (
          <Image
            src={src}
            alt={alt}
            fill
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
            unoptimized={isRemoteMediaUrl(src)}
            className="object-cover transition-transform duration-200 group-hover:scale-[1.02]"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center px-2 text-center text-meta uppercase tracking-label text-muted">
            Image unavailable
          </div>
        )}
        {status && (
          <span className="absolute left-2 top-2 bg-surface/90 px-2 py-1">
            <StatusLabel label={status.label} tone={status.tone} />
          </span>
        )}
      </div>
      <div className="mt-3 border-t border-border pt-3">
        <p className="text-small font-medium text-foreground">{title}</p>
        <p className="mt-1 text-meta uppercase tracking-label text-muted">{meta}</p>
      </div>
    </>
  );

  if (!href) {
    return <div className="group block">{content}</div>;
  }

  return (
    <Link href={href} className="group block">
      {content}
    </Link>
  );
}
