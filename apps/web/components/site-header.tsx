"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/site-config";

const primaryNavLinks = [
  { href: "/stations", label: "Stations" },
  { href: "/archive", label: "Archive" },
  { href: "/map", label: "Map" },
  { href: "/research", label: "Research" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="flex items-center gap-3" onClick={() => setIsMenuOpen(false)}>
          <span className="relative h-10 w-10 shrink-0 overflow-hidden" aria-hidden="true">
            <Image
              src="/brand/auscin-logo.png"
              alt=""
              fill
              sizes="40px"
              className="object-cover object-top"
              priority
            />
          </span>
          <span className="flex items-baseline gap-3">
            <span className="font-display text-heading-lg font-semibold tracking-tight text-foreground">
              {SITE_NAME}
            </span>
            <span className="hidden whitespace-nowrap text-meta uppercase tracking-label text-muted lg:inline">
              {SITE_TAGLINE}
            </span>
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden md:block">
          <ul className="flex items-center gap-6 lg:gap-8">
            {primaryNavLinks.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="text-small text-foreground transition-colors hover:text-accent"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <button
          type="button"
          className="inline-flex items-center justify-center rounded-sm border border-border px-3 py-2 text-small text-foreground md:hidden"
          aria-expanded={isMenuOpen}
          aria-controls="primary-navigation-mobile"
          onClick={() => setIsMenuOpen((open) => !open)}
        >
          <span className="sr-only">
            {isMenuOpen ? "Close navigation menu" : "Open navigation menu"}
          </span>
          <span aria-hidden="true">{isMenuOpen ? "Close" : "Menu"}</span>
        </button>
      </div>

      {isMenuOpen && (
        <nav
          id="primary-navigation-mobile"
          aria-label="Primary"
          className="border-t border-border md:hidden"
        >
          <ul className="mx-auto flex max-w-6xl flex-col gap-1 px-6 py-4">
            {primaryNavLinks.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="block py-2 text-body text-foreground transition-colors hover:text-accent"
                  onClick={() => setIsMenuOpen(false)}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </header>
  );
}
