"""CoastSnap catalogue endpoints (read-only JSON)."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request

from ..catalogue import Catalogue, ObservationFilters
from ..errors import observation_not_found, site_not_found
from ..schemas import (
    CoastSnapObservationResponse,
    CoastSnapSiteResponse,
    DateRangeResponse,
    ErrorResponse,
    MediaType,
    PaginatedResponse,
)

DEFAULT_PAGE_SIZE = 24
"""Matches DEFAULT_PAGE_SIZE in apps/web/lib/pagination.ts."""
MAX_PAGE_SIZE = 100

NOT_FOUND = {404: {"model": ErrorResponse}}

router = APIRouter(prefix="/api/v1/coastsnap", tags=["coastsnap"])


def get_catalogue(request: Request) -> Catalogue:
    return request.app.state.catalogue


CatalogueDep = Annotated[Catalogue, Depends(get_catalogue)]


def _require_site(catalogue: Catalogue, site_id: str) -> None:
    if not catalogue.has_site(site_id):
        raise site_not_found()


@router.get("/sites", response_model=list[CoastSnapSiteResponse])
def list_sites(catalogue: CatalogueDep) -> list[CoastSnapSiteResponse]:
    return catalogue.list_sites()


@router.get("/sites/{site_id}", response_model=CoastSnapSiteResponse, responses=NOT_FOUND)
def get_site(site_id: str, catalogue: CatalogueDep) -> CoastSnapSiteResponse:
    site = catalogue.get_site(site_id)
    if site is None:
        raise site_not_found()
    return site


@router.get(
    "/sites/{site_id}/observations",
    response_model=PaginatedResponse[CoastSnapObservationResponse],
    responses=NOT_FOUND,
)
def list_observations(
    site_id: str,
    catalogue: CatalogueDep,
    media_type: Annotated[Optional[MediaType], Query(alias="mediaType")] = None,
    date_: Annotated[Optional[date], Query(alias="date", description="Local date (site time zone), YYYY-MM-DD")] = None,
    date_from: Annotated[Optional[date], Query(alias="from", description="Inclusive local start date")] = None,
    date_to: Annotated[Optional[date], Query(alias="to", description="Inclusive local end date")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> PaginatedResponse[CoastSnapObservationResponse]:
    _require_site(catalogue, site_id)
    items = catalogue.list_observations(
        site_id, ObservationFilters(media_type=media_type, date=date_, date_from=date_from, date_to=date_to)
    )
    # Same semantics as paginate() in apps/web/lib/pagination.ts: an
    # out-of-range page is clamped to the last page rather than returning nothing.
    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    safe_page = min(page, total_pages)
    start = (safe_page - 1) * page_size
    return PaginatedResponse[CoastSnapObservationResponse](
        items=items[start : start + page_size],
        total=total,
        page=safe_page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/sites/{site_id}/observations/{media_id}",
    response_model=CoastSnapObservationResponse,
    responses=NOT_FOUND,
)
def get_observation(site_id: str, media_id: str, catalogue: CatalogueDep) -> CoastSnapObservationResponse:
    _require_site(catalogue, site_id)
    observation = catalogue.get_observation(site_id, media_id)
    if observation is None:
        raise observation_not_found()
    return observation


@router.get("/sites/{site_id}/date-range", response_model=DateRangeResponse, responses=NOT_FOUND)
def get_date_range(site_id: str, catalogue: CatalogueDep) -> DateRangeResponse:
    _require_site(catalogue, site_id)
    earliest, latest = catalogue.date_range(site_id)
    return DateRangeResponse(earliest=earliest, latest=latest)


