from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>app</html>")
    (d / "assets" / "index-abc123.js").write_text("console.log(1)")
    (d / "sw.js").write_text("// service worker")
    (tmp_path / "secret.txt").write_text("do not serve")
    return d


@pytest.fixture
async def client(dist: Path):
    app = create_app(use_lifespan=False, frontend_dist=dist)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        yield c


async def test_root_serves_index(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.text == "<html>app</html>"
    assert resp.headers["cache-control"] == "no-cache"


async def test_deep_link_falls_back_to_index(client: AsyncClient) -> None:
    resp = await client.get("/today")
    assert resp.status_code == 200
    assert resp.text == "<html>app</html>"


async def test_hashed_assets_are_cached_forever(client: AsyncClient) -> None:
    resp = await client.get("/assets/index-abc123.js")
    assert resp.text == "console.log(1)"
    assert "immutable" in resp.headers["cache-control"]


async def test_service_worker_is_never_cached(client: AsyncClient) -> None:
    resp = await client.get("/sw.js")
    assert resp.text == "// service worker"
    assert resp.headers["cache-control"] == "no-cache"


async def test_unknown_api_route_is_404_not_index(client: AsyncClient) -> None:
    resp = await client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


async def test_path_traversal_cannot_escape_dist(client: AsyncClient) -> None:
    resp = await client.get("/assets/%2E%2E/%2E%2E/secret.txt")
    assert "do not serve" not in resp.text


async def test_no_spa_when_dist_missing(tmp_path: Path) -> None:
    app = create_app(use_lifespan=False, frontend_dist=tmp_path / "nope")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        assert (await c.get("/")).status_code == 404
