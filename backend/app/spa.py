"""Serve the built React app (frontend/dist) from FastAPI, so the whole product is one
service on one origin: no CORS, and cookies work simply.

- Real files (JS, CSS, icons, sw.js, manifest) are served as-is.
- Any other path (/today, /progress...) returns index.html, and React Router shows the
  right screen. This is the usual "single-page app fallback".
- /api/... paths never fall back: an unknown API route is a real 404.

Caching: files in assets/ have a content hash in their name, so they can be cached
forever. Everything else (index.html, sw.js) must be re-checked each time, or phones
would get stuck on an old version.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_IMMUTABLE = "public, max-age=31536000, immutable"
_REVALIDATE = "no-cache"


def mount_spa(app: FastAPI, dist: Path) -> None:
    root = dist.resolve()
    index = root / "index.html"

    # Plain `def` (not async): FastAPI runs it in a thread, so file checks don't block.
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "Not Found")

        candidate = (root / full_path).resolve()
        # is_relative_to blocks path tricks like /../../etc/passwd escaping dist/.
        if full_path and candidate.is_relative_to(root) and candidate.is_file():
            cache = _IMMUTABLE if full_path.startswith("assets/") else _REVALIDATE
            return FileResponse(candidate, headers={"Cache-Control": cache})

        return FileResponse(index, headers={"Cache-Control": _REVALIDATE})
