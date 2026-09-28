"""Media delivery for CoastSnap observations.

Files are located only through the catalogue's trusted `MediaRecord`. The
request supplies an opaque media ID and nothing else, and no request value
ever reaches the filesystem.

Downloads are explicit about product level:

- `/level0` serves the untouched source image, exactly as downloaded from
  Spotteron.
- `/level1` serves the AusCIN provenance copy: Level 0's image bytes plus
  embedded provenance XMP.

Each level has its own registry permission (`level0_download_permitted`,
`level1_download_permitted`, both defaulting to false), its own ETag (that
level's manifest checksum) and an opaque `<media_id>_<level>.<ext>` filename.
`/original` is a DEPRECATED alias for `/level1`, kept temporarily for
compatibility.

Previews and thumbnails never fall back to the original. A missing rendition
is a 404, not a silent substitution of a much larger file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from ..catalogue import DERIVATIVE_CONTENT_TYPE, Catalogue, CatalogueObservation, ProductLevelName
from ..errors import download_not_permitted, media_not_found, media_unavailable, rendition_not_available
from ..media_store import MediaStore, MediaUnavailableError
from ..schemas import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media/coastsnap", tags=["media"])

_EXTENSION_FOR_CONTENT_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

_COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "public, max-age=3600",
}

ERRORS = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def get_catalogue(request: Request) -> Catalogue:
    return request.app.state.catalogue


def get_media_store(request: Request) -> Optional[MediaStore]:
    return request.app.state.media_store


def get_derivatives_store(request: Request) -> Optional[MediaStore]:
    return request.app.state.derivatives_store


CatalogueDep = Annotated[Catalogue, Depends(get_catalogue)]
MediaStoreDep = Annotated[Optional[MediaStore], Depends(get_media_store)]
DerivativesStoreDep = Annotated[Optional[MediaStore], Depends(get_derivatives_store)]


def media_route(path: str, *, deprecated: bool = False):
    """Registers a handler for GET and HEAD. HEAD is registered separately and kept out of the OpenAPI
    schema, because a single GET+HEAD route gives both methods the same operation ID, which is invalid OpenAPI."""

    def register(handler):
        router.head(path, include_in_schema=False)(handler)
        return router.get(path, responses=ERRORS, deprecated=deprecated or None)(handler)

    return register


def _lookup(catalogue: Catalogue, media_id: str) -> CatalogueObservation:
    observation = catalogue.get_media(media_id)
    if observation is None:
        raise media_not_found()
    return observation


def _resolve(store: Optional[MediaStore], relative_path: str) -> Path:
    if store is None:
        raise media_unavailable()
    try:
        return store.resolve(relative_path)
    except MediaUnavailableError as exc:
        logger.warning("Media file unavailable: %s", exc)
        raise media_unavailable() from exc


def _product_download(
    catalogue: Catalogue, store: Optional[MediaStore], media_id: str, level: ProductLevelName,
    extra_headers: Optional[dict[str, str]] = None,
) -> FileResponse:
    observation = _lookup(catalogue, media_id)
    product = observation.media.product(level)
    # Each level has its own registry permission; neither implies the other.
    if not product.download_permitted:
        raise download_not_permitted(level)
    if product.content_type is None:
        raise rendition_not_available(level)
    path = _resolve(store, product.relative_path)
    # The ETag is this level's catalogue checksum, so a file that has changed on disk must not be served
    # under it. A size check is cheap. Re-hashing large files on every request is not, so a changed file
    # of the same size is not detected here; the worker's checksum verification is the control for that.
    if path.stat().st_size != product.file_size:
        logger.warning("Media file size does not match the catalogue record")
        raise media_unavailable()
    return FileResponse(
        path,
        media_type=product.content_type,
        filename=f"{observation.media_id}_{level}{_EXTENSION_FOR_CONTENT_TYPE[product.content_type]}",
        content_disposition_type="attachment",
        headers={**_COMMON_HEADERS, "ETag": f'"{product.sha256}"', **(extra_headers or {})},
    )


@media_route("/{media_id}/level0")
def get_level0(media_id: str, catalogue: CatalogueDep, store: MediaStoreDep) -> FileResponse:
    """Level 0: the untouched source image, exactly as downloaded from Spotteron."""
    return _product_download(catalogue, store, media_id, "level0")


@media_route("/{media_id}/level1")
def get_level1(media_id: str, catalogue: CatalogueDep, store: MediaStoreDep) -> FileResponse:
    """Level 1: the AusCIN provenance copy (Level 0's image bytes plus embedded provenance XMP)."""
    return _product_download(catalogue, store, media_id, "level1")


@media_route("/{media_id}/original", deprecated=True)
def get_original(media_id: str, catalogue: CatalogueDep, store: MediaStoreDep) -> FileResponse:
    """DEPRECATED compatibility alias for `/level1`. It serves exactly the Level 1 response, with the same
    permission, ETag and filename, plus headers pointing clients at the successor endpoint."""
    return _product_download(
        catalogue, store, media_id, "level1",
        extra_headers={"Deprecation": "true", "Link": f'</media/coastsnap/{media_id}/level1>; rel="successor-version"'},
    )


def _derivative(catalogue: Catalogue, store: Optional[MediaStore], media_id: str, kind: str) -> FileResponse:
    observation = _lookup(catalogue, media_id)
    rendition = observation.media.preview if kind == "preview" else observation.media.thumbnail
    if rendition is None:
        raise rendition_not_available(kind)
    path = _resolve(store, rendition.relative_path)
    # Same guard as the original: never serve a changed file under the worker-recorded checksum ETag.
    if path.stat().st_size != rendition.file_size_bytes:
        logger.warning("Derivative file size does not match the derivatives index")
        raise media_unavailable()
    # Served inline with no Content-Disposition filename.
    return FileResponse(
        path,
        media_type=DERIVATIVE_CONTENT_TYPE,
        headers={**_COMMON_HEADERS, "ETag": f'"{rendition.sha256}"'},
    )


@media_route("/{media_id}/preview")
def get_preview(media_id: str, catalogue: CatalogueDep, store: DerivativesStoreDep) -> FileResponse:
    return _derivative(catalogue, store, media_id, "preview")


@media_route("/{media_id}/thumbnail")
def get_thumbnail(media_id: str, catalogue: CatalogueDep, store: DerivativesStoreDep) -> FileResponse:
    return _derivative(catalogue, store, media_id, "thumbnail")
