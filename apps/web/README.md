This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## CoastSnap data source

The `/coastsnap` pages read through one interface, `CoastSnapRepository`
(`data/coastsnap-repository.ts`). The implementation is chosen per request
from the server-side environment:

| `COASTSNAP_API_BASE_URL` | Data source |
|---|---|
| unset or blank (default) | The built-in synthetic sample repository. No API needed. Unit tests always use this. |
| set, e.g. `http://localhost:8000` | The AusCIN catalogue API (`apps/api`), via `data/coastsnap-http-repository.ts` |

Both variables are server-side only (never `NEXT_PUBLIC_`). See `.env.example`.

**Media URLs.** Thumbnails, previews and original downloads are loaded by the
browser directly from the API's `/media/coastsnap/...` endpoints. Every media
URL is resolved against one explicit, browser-reachable media origin:
`COASTSNAP_MEDIA_ORIGIN`, defaulting to the origin of `COASTSNAP_API_BASE_URL`.

- A root-relative URL from the API is resolved against that origin, never
  the Next.js origin at `localhost:3000`.
- An absolute URL on any other origin, or any path other than
  `/media/coastsnap/<this record's media id>/<kind>`, is dropped. The page
  then shows its normal "unavailable" state.

For local development, start the API with `AUSCIN_MEDIA_BASE_URL` set to the
same origin, so it returns absolute URLs that already match. Set
`COASTSNAP_MEDIA_ORIGIN` only when the server reaches the API on an internal
address that browsers can't use.

**Images.** API media is rendered with `next/image`'s `unoptimized` prop, so
`next.config.ts` needs no `remotePatterns` entry:

- the API already serves pre-sized derivatives (thumbnails ≤ 400 px, previews
  ≤ 1600 px)
- Next 16 refuses to optimize images from loopback and private IPs unless
  `dangerouslyAllowLocalIP` is enabled, which carries SSRF risk

**Rendering and failures.**

- All `/coastsnap` routes render at request time, and the HTTP repository
  uses `cache: "no-store"`, so `next build` never contacts the API.
- API 404s become normal "not found" pages.
- Network failures, timeouts, other HTTP errors and malformed responses show
  the `app/coastsnap/error.tsx` "catalogue unavailable" state, with a retry
  action.

Local run against the synthetic API (two terminals):

```powershell
# apps/api — generate synthetic media once, then start the fixture-backed API
.\.venv\Scripts\python.exe tests\fixtures\synthetic_media.py .local-media
$env:COASTSNAP_SITE_REGISTRY_PATH = "tests/fixtures/coastsnap/sites-registry.json"
$env:COASTSNAP_MANIFEST_PATH = "tests/fixtures/coastsnap/manifest.json"
$env:COASTSNAP_DERIVATIVES_INDEX_PATH = "tests/fixtures/coastsnap/derivatives-index.json"
$env:COASTSNAP_MEDIA_ROOT = ".local-media"
$env:AUSCIN_MEDIA_BASE_URL = "http://localhost:8000"
.\.venv\Scripts\python.exe -m uvicorn auscin_api.main:create_app --factory --port 8000

# apps/web
$env:COASTSNAP_API_BASE_URL = "http://localhost:8000"
npm run dev
```

The same two servers are available as the `api (synthetic fixtures)` and
`web (CoastSnap API)` configurations in `.claude/launch.json`.

**Footer wording.** The global footer follows the same switch:

- **Sample mode:** it says all station, camera, media and CoastSnap records
  are synthetic development data.
- **API mode:** it says CoastSnap observations are served by the AusCIN
  catalogue API, and that the other records are still sample data.

It never claims production data, because nothing in the configuration says
the catalogue is production. Static routes (for example `/` and `/about`)
are prerendered, so their footer reflects the environment at `next build`.
Set `COASTSNAP_API_BASE_URL` for the build as well as at runtime to keep
every page consistent. The `/coastsnap` routes always use the runtime value.

**Dimensions.** Width and height come from the API when the worker's
derivatives index recorded them. Otherwise the detail page shows "Not
recorded".

**End-to-end check.** `scripts/coastsnap_e2e_smoke.py` builds this app, runs
`next start` against a FastAPI catalogue fed by worker-generated derivatives,
and verifies the CoastSnap pages, preview and download. See "Local end-to-end
workflow" in `apps/api/README.md`.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
