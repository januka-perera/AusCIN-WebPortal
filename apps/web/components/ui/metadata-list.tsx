import type { ReactNode } from "react";

export type MetadataItem = {
  label: string;
  value: ReactNode;
};

type MetadataListProps = {
  items: MetadataItem[];
};

/** A label/value list for capture, station and camera metadata, set off by thin rules. */
export function MetadataList({ items }: MetadataListProps) {
  return (
    <dl className="divide-y divide-border border-t border-border">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline justify-between gap-4 py-2">
          <dt className="text-meta uppercase tracking-label text-muted">{item.label}</dt>
          <dd className="text-right text-small text-foreground">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
