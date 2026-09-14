"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ImageCard } from "@/components/ui/image-card";
import { ImageCardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { MetadataList } from "@/components/ui/metadata-list";
import { SectionHeading } from "@/components/ui/section-heading";
import { StatusLabel, type StatusTone } from "@/components/ui/status-label";

const colorSwatches: Array<{ name: string; token: string; className: string }> = [
  { name: "Background", token: "--color-background", className: "bg-background" },
  { name: "Surface", token: "--color-surface", className: "bg-surface border border-border" },
  { name: "Border", token: "--color-border", className: "bg-border" },
  { name: "Foreground", token: "--color-foreground", className: "bg-foreground" },
  { name: "Muted", token: "--color-muted", className: "bg-muted" },
  { name: "Accent", token: "--color-accent", className: "bg-accent" },
  { name: "Accent strong", token: "--color-accent-strong", className: "bg-accent-strong" },
  { name: "Secondary accent", token: "--color-secondary-accent", className: "bg-secondary-accent" },
];

const typeSamples: Array<{ name: string; className: string; sample: string }> = [
  { name: "Display / lg", className: "font-display text-display-lg text-foreground", sample: "Coastal change, observed" },
  { name: "Display / md", className: "font-display text-display-md text-foreground", sample: "Coastal change, observed" },
  { name: "Heading / lg", className: "font-display text-heading-lg text-foreground", sample: "Station overview" },
  { name: "Heading / md", className: "font-display text-heading-md text-foreground", sample: "Latest observations" },
  { name: "Body", className: "font-sans text-body text-foreground", sample: "Fixed camera and lidar stations across Australia's coastline." },
  { name: "Small", className: "font-sans text-small text-muted", sample: "Station, camera and capture metadata" },
  { name: "Meta / label", className: "font-sans text-meta uppercase tracking-label text-muted", sample: "Station ID · AVAL01" },
];

const spacingSamples: Array<{ name: string; className: string }> = [
  { name: "Gutter", className: "w-[var(--spacing-gutter)]" },
  { name: "Section y", className: "w-[var(--spacing-section-y)]" },
  { name: "Section y / lg", className: "w-[var(--spacing-section-y-lg)]" },
];

const stationMetadata = [
  { label: "Station ID", value: "AVAL01" },
  { label: "Region", value: "Northern Beaches, NSW" },
  { label: "Camera type", value: "Fixed (HD)" },
  { label: "Elevation", value: "12 m AHD" },
  { label: "Operational", value: "Since 2016" },
];

const statusTones: Array<{ label: string; tone: StatusTone }> = [
  { label: "Active", tone: "positive" },
  { label: "Processing", tone: "neutral" },
  { label: "Embargoed", tone: "caution" },
  { label: "Restricted", tone: "restricted" },
];

export default function DesignSystemPage() {
  const [retryCount, setRetryCount] = useState(0);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-16 px-6 py-16">
      <div>
        <p className="text-meta uppercase tracking-label text-accent">Internal reference</p>
        <h1 className="mt-2 font-display text-display-md text-foreground">AusCIN design system</h1>
        <p className="mt-4 max-w-2xl text-body text-muted">
          A living reference for the tokens and reusable components introduced in this pass.
          Not a page for public visitors — use it to check colour, type, spacing and component
          behaviour while building real pages.
        </p>
      </div>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Colour</h2>
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          {colorSwatches.map((swatch) => (
            <div key={swatch.name} className="flex flex-col gap-2">
              <div className={`h-16 w-full rounded-sm ${swatch.className}`} />
              <p className="text-small text-foreground">{swatch.name}</p>
              <p className="font-mono text-meta text-muted">{swatch.token}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Typography</h2>
        <div className="flex flex-col gap-6">
          {typeSamples.map((sample) => (
            <div key={sample.name} className="border-t border-border pt-4">
              <p className="text-meta uppercase tracking-label text-muted">{sample.name}</p>
              <p className={`mt-2 ${sample.className}`}>{sample.sample}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Spacing</h2>
        <div className="flex flex-col gap-3">
          {spacingSamples.map((sample) => (
            <div key={sample.name} className="flex items-center gap-4">
              <p className="w-32 shrink-0 text-small text-muted">{sample.name}</p>
              <div className={`h-3 bg-accent/40 ${sample.className}`} />
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Buttons</h2>
        <div className="flex flex-wrap items-center gap-4">
          <Button href="#">Primary action</Button>
          <Button href="#" variant="secondary">
            Secondary action
          </Button>
          <Button disabled>Disabled</Button>
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Metadata rows</h2>
        <div className="max-w-sm">
          <MetadataList items={stationMetadata} />
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Image cards</h2>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          <ImageCard
            href="#"
            src="/brand/auscin-logo.png"
            alt="Placeholder thumbnail"
            title="Avalon Beach"
            meta="14 Feb 2024, 07:00 AEDT"
          />
          <ImageCard
            href="#"
            src="/brand/auscin-logo.png"
            alt="Placeholder thumbnail"
            title="Bondi Beach"
            meta="14 Feb 2024, 07:08 AEDT"
            status={{ label: "Processing", tone: "neutral" }}
          />
          <ImageCard
            href="#"
            src="/brand/auscin-logo.png"
            alt="Placeholder thumbnail"
            title="Cottesloe"
            meta="14 Feb 2024, 07:11 AWST"
            status={{ label: "Restricted", tone: "restricted" }}
          />
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Section heading</h2>
        <SectionHeading
          eyebrow="Stations"
          title="Coastal cameras across Australia"
          description="A national network of fixed camera and lidar stations, existing infrastructure and CoastSnap sites."
          action={{ label: "View all stations", href: "#" }}
        />
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Status labels</h2>
        <div className="flex flex-wrap gap-6">
          {statusTones.map((status) => (
            <StatusLabel key={status.label} label={status.label} tone={status.tone} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Loading states</h2>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          <ImageCardSkeleton />
          <ImageCardSkeleton />
          <div className="flex flex-col gap-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Empty state</h2>
        <EmptyState
          title="No observations match these filters"
          description="Try widening the date range or choosing a different camera."
          action={{ label: "Clear filters", href: "#" }}
        />
      </section>

      <section className="flex flex-col gap-6">
        <h2 className="font-display text-heading-lg text-foreground">Error state</h2>
        <ErrorState
          title="Couldn't load this station's archive"
          description="Check your connection and try again."
          onRetry={() => setRetryCount((count) => count + 1)}
        />
        <p className="text-small text-muted">Retried {retryCount} time{retryCount === 1 ? "" : "s"}.</p>
      </section>
    </div>
  );
}
