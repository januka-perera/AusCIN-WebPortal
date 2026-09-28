"""Media delivery for CoastSnap observations.

Files are located only through the catalogue's trusted `MediaRecord`. The
request supplies an opaque media ID and nothing else, and no request value
ever reaches the filesystem.

The download policy is provisional: `original` serves the **Level 1** product,
which is the Level 0 image bytes plus embedded AusCIN provenance metadata. Whether
the public download should be Level 0 or Level 1 is still an open decision. See
docs/implementation/coastsnap-single-site-publication.md.

Previews and thumbnails never fall back to the original. A missing rendition
is a 404, not a silent substitution of a much larger file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from ..catalogue import DERIVATIVE_CONTENT_TYPE, Catalogue, CatalogueObservation
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


@router.api_route("/{media_id}/original", methods=["GET", "HEAD"], responses=ERRORS)
def get_original(media_id: str, catalogue: CatalogueDep, store: MediaStoreDep) -> FileResponse:
    observation = _lookup(catalogue, media_id)
    media = observation.media
    if not media.original_download_permitted:
        raise download_not_permitted()
    if media.level1_content_type is None:
        raise rendition_not_available("original")
    path = _resolve(store, media.level1_relative_path)
    # The ETag is the catalogue checksum, so a file that has changed on disk must not be served under it.
    # A size check is cheap. Re-hashing large files on every request is not, so a changed file of the
    # same size is not detected here; the worker's checksum verification is the control for that.
    if path.stat().st_size != media.level1_file_size:
        logger.warning("Media file size does not match the catalogue record")
        raise media_unavailable()
    return FileResponse(
        path,
        media_type=media.level1_content_type,
        filename=f"{observation.media_id}{_EXTENSION_FOR_CONTENT_TYPE[media.level1_content_type]}",
        content_disposition_type="attachment",
        headers={**_COMMON_HEADERS, "ETag": f'"{media.level1_sha256}"'},
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


@router.api_route("/{media_id}/preview", methods=["GET", "HEAD"], responses=ERRORS)
def get_preview(media_id: str, catalogue: CatalogueDep, store: DerivativesStoreDep) -> FileResponse:
    return _derivative(catalogue, store, media_id, "preview")


@router.api_route("/{media_id}/thumbnail", methods=["GET", "HEAD"], responses=ERRORS)
def get_thumbnail(media_id: str, catalogue: CatalogueDep, store: DerivativesStoreDep) -> FileResponse:
    return _derivative(catalogue, store, media_id, "thumbnail")
