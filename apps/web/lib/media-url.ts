/**
 * True for an absolute http(s) URL, which in this app always means media served
 * by the catalogue API, as opposed to a same-origin `/sample-media/...` path.
 *
 * API media is rendered with `next/image`'s `unoptimized` prop. The API already
 * serves pre-sized thumbnails (≤ 400 px) and previews (≤ 1600 px). Routing them
 * through the Next.js optimizer would need a `remotePatterns` entry per
 * environment, and in local development it's refused anyway: Next 16 blocks
 * optimizing images from private and loopback addresses unless
 * `dangerouslyAllowLocalIP` is on, which carries SSRF risk. With `unoptimized`,
 * the browser loads the API URL directly, and `next.config.ts` needs no
 * remote-host allowance at all.
 */
export function isRemoteMediaUrl(src: string): boolean {
  return /^https?:\/\//i.test(src);
}
