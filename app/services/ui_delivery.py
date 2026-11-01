"""Targeted response compression and cache rules for the UI payloads."""

from __future__ import annotations

import re

from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send


_MODEL_OPTIONS_PATH = re.compile(r"/api/v1/model-options/[^/]+\Z")
_HASHED_ASSET_PATH = re.compile(
    r"/assets/[^/]+-[A-Za-z0-9_-]{8,}\.(?:js|css)\Z"
)
_COMPRESSIBLE_METHODS = frozenset({"GET", "HEAD"})
# Vite names every emitted asset by content hash (``index-B5T8CBC4.js``).
_HASHED_BUILD_FILE = re.compile(r"assets/[^/]+-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+\Z")
_HASHED_CACHE_CONTROL = "public, max-age=31536000, immutable"
_SHELL_CACHE_CONTROL = "no-cache"


def _is_startup_payload(scope: Scope) -> bool:
    """Return whether this request is one of the bounded UI payload routes."""
    if scope.get("type") != "http" or scope.get("method", "").upper() not in _COMPRESSIBLE_METHODS:
        return False

    path = scope.get("path", "")
    return (
        path == "/api/v1/models"
        or _MODEL_OPTIONS_PATH.fullmatch(path) is not None
        or _HASHED_ASSET_PATH.fullmatch(path) is not None
    )


class UIStartupGZipMiddleware:
    """Apply Starlette gzip negotiation only to large startup UI payloads.

    Starlette remains responsible for compression, content-encoding handling,
    and ``Vary: Accept-Encoding``. The allowlist avoids buffering or changing
    delivery for generated media, downloads, thumbnails, and event streams.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=1024, compresslevel=4)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if _is_startup_payload(scope):
            await self.gzip(scope, receive, send)
            return

        await self.app(scope, receive, send)


class UIStaticFiles(StaticFiles):
    """Serve the React build so a browser never keeps an earlier build's shell.

    Hashed bundles never change and may be cached for a year. ``index.html``
    and the other unhashed root files name whichever bundles are current.
    Without a Cache-Control header, browsers cache them heuristically. After a
    rebuild, or when another Maestro install later serves the same port, the
    tab then runs a previous build. Its lazily loaded screens (Settings,
    Editor, Director, Worlds) are gone from disk, so opening one shows a
    black screen. The shell is therefore revalidated on every load, which
    costs one 304 when nothing changed.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            relative = path.replace("\\", "/")
            response.headers["Cache-Control"] = (
                _HASHED_CACHE_CONTROL
                if _HASHED_BUILD_FILE.fullmatch(relative)
                else _SHELL_CACHE_CONTROL
            )
        return response
