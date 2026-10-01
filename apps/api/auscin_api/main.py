"""Application factory.

Run locally with:
    uvicorn auscin_api.main:create_app --factory --reload
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Request

from .catalogue import Catalogue, load_multi_site_catalogue
from .errors import register_error_handlers
from .media_store import LocalMediaStore, MediaStore
from .routes import coastsnap, media
from .schemas import HealthResponse
from .settings import Settings, SettingsError


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Builds the app. The catalogue and media store are set up eagerly, so invalid
    or unsafe inputs fail at startup rather than on a request."""
    settings = settings or Settings.from_env()

    media_store: Optional[MediaStore] = None
    derivatives_store: Optional[MediaStore] = None
    if settings.media_root is not None:
        try:
            media_store = LocalMediaStore(settings.media_root)
        except ValueError as exc:
            raise SettingsError(f"COASTSNAP_MEDIA_ROOT is invalid: {exc}") from exc
        derivatives_store = media_store
    if settings.derivatives_root is not None:
        try:
            derivatives_store = LocalMediaStore(settings.derivatives_root)
        except ValueError as exc:
            raise SettingsError(f"COASTSNAP_DERIVATIVES_ROOT is invalid: {exc}") from exc

    catalogue = load_multi_site_catalogue(
        settings.site_registry_path,
        settings.manifest_paths,
        settings.derivatives_index_paths,
        media_enabled=media_store is not None,
        media_base_url=settings.media_base_url,
    )

    app = FastAPI(title="AusCIN catalogue API", version="0.1.0")
    app.state.settings = settings
    app.state.catalogue = catalogue
    app.state.media_store = media_store
    app.state.derivatives_store = derivatives_store
    register_error_handlers(app)

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    def health(request: Request) -> HealthResponse:
        loaded: Catalogue = request.app.state.catalogue
        return HealthResponse(
            status="ok",
            public_site_count=loaded.public_site_count,
            public_observation_count=loaded.public_observation_count,
        )

    app.include_router(coastsnap.router)
    app.include_router(media.router)
    return app
