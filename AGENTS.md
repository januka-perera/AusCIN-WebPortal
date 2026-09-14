# AusCIN Coastal Media Portal

## Project context

This repository contains the public-facing AusCIN (Australian Coastal Intelligence Network) web portal.

AusCIN coordinates coastal observations from fixed camera and lidar stations, existing camera infrastructure and CoastSnap sites. The portal will allow public users and researchers to browse coastal images, composites and time-lapse videos, filter observations by station, camera, date and time, inspect metadata and download permitted files.

The first interface should support:

* a station overview page
* station detail pages
* an image and video archive
* date and time filtering
* image previews and detail pages
* time-lapse video playback
* original-file downloads where permitted
* station, camera and capture metadata
* links to related scientific data products

The portal is a media catalogue and delivery service, not a raw filesystem browser.

## Deployment context

Development is performed on Windows using PowerShell, VS Code, Git and Codex CLI. WSL2 is not required.

The production application will eventually run on a Nirin VM. Raw imagery and long-term products remain in the NCI project storage under `/g/data/qu34`. The local development environment must not connect directly to production data.

Use a small sample dataset under `data/sample` during development.

## Intended architecture

* `apps/web`: Next.js and TypeScript frontend
* `apps/api`: FastAPI backend when the backend is introduced
* `apps/worker`: indexing, thumbnail and media-processing workers
* PostgreSQL: media and station metadata
* Redis or another queue: background processing jobs
* FFmpeg: video inspection and transcoding
* Nginx or an equivalent media gateway: reverse proxy and range-based media delivery
* Docker may be used for local supporting services and reproducible integration testing

Start with the frontend if the task only concerns the interface. Do not create backend infrastructure prematurely.

## Repository and file rules

* Keep source code, configuration templates, tests and documentation in Git.
* Do not commit raw images, original videos, generated derivatives, databases, logs or temporary processing files.
* Do not commit passwords, API keys, SSH keys, certificates or real `.env` files.
* Use `.env.example` for required configuration names.
* Do not hard-code Windows-specific paths into application code.
* Keep generated and runtime data outside the source tree where practical.
* Use UTC internally for timestamps and make the displayed time zone explicit.

## Storage and security rules

* Never expose arbitrary filesystem paths through the API or frontend.
* Use opaque media IDs and resolve paths through trusted catalogue records.
* Validate and normalise all media paths and confirm that resolved paths remain within an approved publication root.
* Never access `/g/data/qu34` during local development.
* Use read-only access for published media where possible.
* Treat public, embargoed, project-only and restricted media as different visibility classes.
* Do not make a media file public merely because it exists on a readable filesystem.

## Media-performance rules

* Gallery cards must use thumbnails, not original files.
* Detail pages should use browser-sized previews unless the user explicitly requests the original.
* Generate thumbnails, previews and video posters asynchronously.
* Use pagination or virtualisation for large result sets.
* Use cursor-based pagination for growing time-series archives.
* Support HTTP range requests for video and large downloads.
* Use adaptive streaming for long or high-resolution videos where appropriate.
* Do not scan large `/g/data` directory trees during a user request.
* Maintain an indexed catalogue of media metadata.

## Design rules

Read `design_reference.md` and the material in `docs/design` before changing the visual design.

The interface should feel editorial, scientific, calm, image-led and deliberately designed. The coastal imagery and observation metadata should be the focus.

Avoid generic AI-generated styling, including excessive gradients, glassmorphism, glowing cards, oversized SaaS hero sections, arbitrary rounded panels, decorative blobs, dense dashboard layouts and generic marketing copy.

Do not copy the branding, text, logos or distinctive layouts of reference websites. Adapt useful interaction patterns into an original AusCIN design.

## Coding practices

* Inspect the existing code before editing.
* Make the smallest coherent change that satisfies the request.
* Preserve established component, naming and styling conventions.
* Use TypeScript types and Python type hints.
* Prefer reusable components over duplicated page-specific markup.
* Keep API, database and media-delivery responsibilities separate.
* Validate external input at API boundaries.
* Add or update tests for new behaviour.
* Include loading, empty, unavailable and error states in user-facing features.
* Do not silently change API contracts or database schemas without documenting the change.

## Development workflow

Before implementation:

1. Inspect the relevant files.
2. Explain the proposed approach and identify assumptions.
3. Check whether existing components or utilities can be reused.

After implementation:

1. Run relevant tests and linting.
2. Check the page in a browser at desktop and mobile widths when UI changes are made.
3. Inspect the Git diff.
4. Report any remaining limitations or unverified behaviour.

Use focused tasks. Do not combine unrelated frontend, database, ingestion and deployment changes unless explicitly requested.

## Useful local commands

Use PowerShell commands on the Windows host unless a command is explicitly being run inside a container.

Typical frontend commands:

```powershell
npm install
npm run dev
npm run lint
npm run build
```

If Docker Compose is introduced:

```powershell
docker compose up --build
docker compose ps
docker compose down
```

## Visual references

Generated interface concepts are listed in `design_reference.md`. They are references for hierarchy, page structure and interaction patterns, not assets to copy directly.
