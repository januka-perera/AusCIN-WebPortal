import Image from "next/image";
import { Button } from "@/components/ui/button";
import { SectionHeading } from "@/components/ui/section-heading";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/site-config";

const capabilities = [
  {
    title: "Browse by station",
    description:
      "Move from a national overview to an individual camera or lidar station, with its location, cameras and operating status.",
  },
  {
    title: "Filter by date and time",
    description:
      "Step through an archive by date range and time of day to follow how a stretch of coastline changes.",
  },
  {
    title: "Inspect capture metadata",
    description:
      "Every image and video carries its station, camera, capture time and technical detail alongside the observation.",
  },
  {
    title: "Download permitted originals",
    description:
      "Where a file's visibility allows it, download the original image or video for research or reporting use.",
  },
];

export default function Home() {
  return (
    <>
      <section className="border-b border-border bg-surface">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 sm:py-24 lg:grid-cols-[3fr_2fr] lg:items-center lg:gap-16">
          <div>
            <p className="text-meta uppercase tracking-label text-accent">
              Coastal observation network
            </p>
            <h1 className="mt-4 font-display text-display-md text-foreground sm:text-display-lg">
              A continuous record of Australia&apos;s coastline.
            </h1>
            <p className="mt-6 max-w-xl text-body text-muted">
              AusCIN coordinates imagery from fixed coastal camera and lidar stations, existing
              camera infrastructure and CoastSnap sites, and makes it available for research,
              coastal management and public understanding.
            </p>
            <div className="mt-8">
              <Button href="/stations">
                Explore stations
                <span aria-hidden="true">&rarr;</span>
              </Button>
            </div>
          </div>

          <div className="flex justify-center lg:justify-end">
            <Image
              src="/brand/auscin-logo.png"
              alt={`${SITE_NAME} — ${SITE_TAGLINE} logo`}
              width={961}
              height={1264}
              className="h-72 w-auto sm:h-80"
              priority
            />
          </div>
        </div>
      </section>

      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <SectionHeading title="What you can do here" />
          <dl className="mt-8 grid gap-8 sm:grid-cols-2">
            {capabilities.map((item) => (
              <div key={item.title} className="border-t border-border pt-4">
                <dt className="font-display text-heading-md text-foreground">{item.title}</dt>
                <dd className="mt-2 text-small text-muted">{item.description}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section>
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 sm:py-20 lg:grid-cols-[2fr_3fr] lg:gap-16">
          <h2 className="font-display text-heading-lg text-foreground">Why AusCIN exists</h2>
          <div className="space-y-4 text-body text-muted">
            <p>
              Coastlines change on time scales that are easy to miss day to day but significant
              over months and years. AusCIN builds a long-term, openly accessible archive of
              coastal imagery so that this change can be observed, measured and understood.
            </p>
            <p>
              The network brings together purpose-built camera and lidar stations with existing
              infrastructure and community CoastSnap sites, presenting them through a single
              catalogue rather than as scattered, one-off feeds.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
