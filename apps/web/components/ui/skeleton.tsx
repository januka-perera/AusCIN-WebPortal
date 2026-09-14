import { cn } from "@/lib/cn";

/** A quiet pulsing placeholder block for content that is still loading. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse bg-border/60", className)} />;
}

/** A loading placeholder shaped like an ImageCard, for gallery grids. */
export function ImageCardSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="aspect-[4/3] w-full" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/3" />
    </div>
  );
}
