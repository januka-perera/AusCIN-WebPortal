import type { Metadata } from "next";
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google";
import { SiteHeader } from "@/components/site-header";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/site-config";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: `${SITE_NAME} — ${SITE_TAGLINE}`,
  description:
    "Browse coastal observations — images, time-lapse video and capture metadata — from Australian fixed-camera and lidar stations, CoastSnap sites and cameras of opportunity.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${sourceSerif.variable} h-full`}
    >
      <body className="flex min-h-full flex-col bg-background font-sans text-body text-foreground antialiased">
        <SiteHeader />
        <main className="flex flex-1 flex-col">{children}</main>
        <footer className="border-t border-border">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-10 text-small text-muted sm:flex-row sm:items-center sm:justify-between">
            <p>
              {SITE_NAME} — {SITE_TAGLINE}
            </p>
            <p>Development build — station, camera and media records are synthetic sample data.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
