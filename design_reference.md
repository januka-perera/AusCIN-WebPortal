# AusCIN design reference

## Purpose

AusCIN is a public coastal observation portal. It will present images and videos collected from fixed coastal camera stations, lidar stations, existing camera infrastructure and CoastSnap sites.

Users should be able to discover stations, browse observations by date and time, filter by station, camera and media type, view previews, inspect metadata, download permitted original files and find related scientific datasets.

The design must feel like a credible scientific image archive with an editorial quality of presentation. It should not feel like a generic software dashboard, stock-photo website or automatically generated AI landing page.

## Generated interface references

The generated mockups are available in the workspace's `generated_images` directory. Copy them into the repository if they are to be used as local references, preferably under `docs/design/references/`.

### Station overview

Filename: `exec-bf1ca39e-40e6-47e3-9335-71053fd8edb7.png`

Use it as a reference for a restrained landing page, a large coastal observation image, station cards, a station map, latest observations and a short explanation of the network's purpose.

### Time-series gallery

Filename: `exec-bd0ef458-67bf-4811-a4e7-2c23c561231e.png`

Use it as a reference for a station-specific archive, date and time navigation, time-labelled image thumbnails, station information, a selected-image preview and related imagery.

### Image and video detail page

Filename: `exec-fb7b2532-3a0f-47a0-bc06-b040deed9d32.png`

Use it as a reference for a large selected image, capture metadata, download actions, nearby observations and a related time-lapse video.

These filenames are generated asset identifiers. If copied into the repository, they may be renamed to `station-overview.png`, `time-series-gallery.png` and `image-video-detail.png`, with this document retaining their descriptive roles.

## Core design direction

The interface should be editorial, scientific, calm, image-led and deliberately designed. Coastal imagery and observation metadata are the focus.

Use strong image hierarchy, generous but purposeful whitespace, clear metadata, restrained colour and useful date and time controls.

Avoid generic AI-generated styling, including:

* purple-blue gradients
* glassmorphism
* glowing borders and cards
* decorative blobs
* oversized generic SaaS hero sections
* arbitrary rounded panels
* excessive pill-shaped controls
* identical card grids on every page
* dense dashboard layouts
* generic marketing copy
* decorative animation that does not help users understand observations

## Visual system

### Colour

Use a restrained coastal palette:

* warm white, sand or pale grey backgrounds
* deep charcoal or navy text
* one muted ocean blue or teal accent
* occasional rust, ochre or kelp-toned secondary accent

Colours should support the imagery rather than compete with it. Do not use multiple unrelated accent colours, neon colours or strong gradients behind text.

### Typography

Use a considered typographic system with a clear distinction between display headings, section headings, body text, metadata labels and timestamps.

A restrained serif or humanist display face may be paired with a highly legible sans-serif for controls and metadata. Avoid oversized typography used only to imitate a marketing landing page.

### Layout

Prefer clear grid alignment, generous margins, thin rules, subtle borders, image-led cards and quiet hover states. Asymmetrical editorial layouts are acceptable when they improve image hierarchy.

Avoid placing every section inside a rounded card. Do not use floating panels, decorative shapes or repeated three-column card grids without a clear information reason.

## Interaction design

Users should be able to filter the archive by:

* station
* camera
* date range
* time of day
* media type
* availability or processing status where useful

Filters should be compact and understandable. The current search state should be represented in the URL so results can be bookmarked and shared.

Use progressive disclosure. Show the most important information first and reveal technical detail when needed.

For example:

* gallery card: image, station, date and time
* detail page: resolution, file size, camera and conditions
* advanced metadata: provenance, technical fields and related datasets

Use explicit action labels such as `Download original`, `View time-lapse` and `Explore this station`. Do not rely on unlabeled icons.

## Page guidance

### Landing page

Recommended order:

1. concise navigation
2. one strong coastal observation image
3. short explanation of the network
4. explore stations action
5. selected stations or latest observations
6. map or regional overview
7. research and data-access links

The landing page should lead users into the archive quickly. It should not be a generic hero section followed by unrelated marketing cards.

### Station page

Show the station name, location, representative recent image, description, camera list, operating status, date and time controls, archive entry point and map location.

### Time-series gallery

Show the selected station and camera, date range, time context, media type, thumbnails labelled with capture times, selected observation and pagination or virtualised loading for large result sets.

Do not load original images into the gallery.

### Image or video detail page

Show a large preview or player, station, camera, capture date, capture time, time zone, dimensions or duration, file size, download controls, nearby observations, related products and provenance or licence information.

## Performance-aware visual design

The archive may contain very large numbers of images and videos.

* Use thumbnails for grids.
* Lazy-load images outside the viewport.
* Do not render thousands of cards at once.
* Use cursor pagination or virtualisation for large archives.
* Display placeholders while previews load.
* Keep the initial page payload small.
* Do not make the browser scan directories.
* Make unavailable or processing media visually clear.

## Accessibility

Include sufficient colour contrast, keyboard navigation, visible focus states, descriptive alternative text, accessible labels for icon buttons, captions or descriptions for video where appropriate and layouts that work without hover.

Every page should have meaningful loading, empty, unavailable and error states.

## Use of external references

External websites and generated mockups may inform layout hierarchy, filter behaviour, timeline patterns, archive navigation, metadata presentation and download workflows.

Do not copy logos, branding, text, distinctive illustrations, exact layouts or proprietary visual identity. The final interface should be recognisably AusCIN: an Australian coastal observation archive with its own identity and clear scientific purpose.

## Design-review prompts for Codex

Before implementing a new page, ask Codex to identify which reference images and principles apply. After implementation, ask it to compare the result against this document and report differences in image hierarchy, spacing, typography, colour balance, filter clarity, accessibility and responsive behaviour.
