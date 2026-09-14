import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary";

const baseStyles =
  "inline-flex items-center justify-center gap-2 rounded-sm px-5 py-3 text-small font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const variantStyles: Record<Variant, string> = {
  primary:
    "border border-accent bg-accent text-accent-foreground hover:bg-accent-strong hover:border-accent-strong",
  secondary:
    "border border-border bg-transparent text-foreground hover:border-accent hover:text-accent",
};

type ButtonAsButton = { variant?: Variant; href?: undefined } & ButtonHTMLAttributes<HTMLButtonElement>;

type ButtonAsLink = { variant?: Variant; href: string } & AnchorHTMLAttributes<HTMLAnchorElement>;

export type ButtonProps = ButtonAsButton | ButtonAsLink;

export function Button(props: ButtonProps) {
  const { variant = "primary", className, children, ...rest } = props;
  const styles = cn(baseStyles, variantStyles[variant], className);

  if (typeof rest.href === "string") {
    const { href, ...linkRest } = rest;
    return (
      <Link href={href} {...linkRest} className={styles}>
        {children}
      </Link>
    );
  }

  const { type = "button", ...buttonRest } = rest as ButtonHTMLAttributes<HTMLButtonElement>;
  return (
    <button type={type} {...buttonRest} className={styles}>
      {children}
    </button>
  );
}
