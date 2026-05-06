from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.conftest import mock_get_artwork

PATCH_PROJECTS = "app.routers.projects.get_artwork"
PATCH_PLACES = "app.routers.places.get_artwork"

ALL_IDS = [27992, 16487, 14620, 20684, 28560, 80607, 111628, 100472, 24645, 60755]


# ── helpers ───────────────────────────────────────────────────────────────────

async def make_project(client: AsyncClient, auth: dict, name: str = "Test") -> dict:
    resp = await client.post("/projects", json={"name": name}, headers=auth)
    assert resp.status_code == 201
    return resp.json()


async def add_place(
    client: AsyncClient, auth: dict, project_id: int, external_id: int = 27992
) -> dict:
    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        resp = await client.post(
            f"/projects/{project_id}/places",
            json={"external_id": external_id},
            headers=auth,
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_places_empty(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    resp = await client.get(f"/projects/{proj['id']}/places", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_list_places_pagination(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    for ext_id in ALL_IDS[:3]:
        await add_place(client, auth, proj["id"], ext_id)

    resp = await client.get(f"/projects/{proj['id']}/places?page=1&page_size=2", headers=auth)
    body = resp.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2


async def test_list_places_filter_visited(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    place = await add_place(client, auth, proj["id"], 27992)
    await add_place(client, auth, proj["id"], 16487)

    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        await client.patch(
            f"/projects/{proj['id']}/places/{place['id']}",
            json={"is_visited": True},
            headers=auth,
        )

    resp = await client.get(f"/projects/{proj['id']}/places?visited=true", headers=auth)
    assert resp.json()["total"] == 1

    resp = await client.get(f"/projects/{proj['id']}/places?visited=false", headers=auth)
    assert resp.json()["total"] == 1


async def test_list_places_project_not_found(client: AsyncClient, auth: dict):
    resp = await client.get("/projects/9999/places", headers=auth)
    assert resp.status_code == 404


# ── add place ─────────────────────────────────────────────────────────────────

async def test_add_place_success(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    place = await add_place(client, auth, proj["id"], 27992)
    assert place["external_id"] == 27992
    assert place["title"] == "A Sunday on La Grande Jatte"
    assert place["is_visited"] is False
    assert place["notes"] is None


async def test_add_place_stores_image_url(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    place = await add_place(client, auth, proj["id"], 27992)
    assert place["image_url"] is not None
    assert "img-001" in place["image_url"]


async def test_add_place_invalid_artwork(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    with patch(PATCH_PLACES, return_value=None):
        resp = await client.post(
            f"/projects/{proj['id']}/places",
            json={"external_id": 999999},
            headers=auth,
        )
    assert resp.status_code == 422


async def test_add_duplicate_place(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    await add_place(client, auth, proj["id"], 27992)

    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        resp = await client.post(
            f"/projects/{proj['id']}/places",
            json={"external_id": 27992},
            headers=auth,
        )
    assert resp.status_code == 409


async def test_add_place_to_nonexistent_project(client: AsyncClient, auth: dict):
    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        resp = await client.post(
            "/projects/9999/places",
            json={"external_id": 27992},
            headers=auth,
        )
    assert resp.status_code == 404


async def test_add_place_exceeds_limit(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)

    for ext_id in ALL_IDS:
        await add_place(client, auth, proj["id"], ext_id)

    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        resp = await client.post(
            f"/projects/{proj['id']}/places",
            json={"external_id": 11272},
            headers=auth,
        )
    assert resp.status_code == 422


# ── get single place ──────────────────────────────────────────────────────────

async def test_get_place_success(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    place = await add_place(client, auth, proj["id"], 27992)

    resp = await client.get(f"/projects/{proj['id']}/places/{place['id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["id"] == place["id"]


async def test_get_place_not_found(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    resp = await client.get(f"/projects/{proj['id']}/places/9999", headers=auth)
    assert resp.status_code == 404


async def test_get_place_wrong_project(client: AsyncClient, auth: dict):
    proj1 = await make_project(client, auth, "P1")
    proj2 = await make_project(client, auth, "P2")
    place = await add_place(client, auth, proj1["id"], 27992)

    resp = await client.get(f"/projects/{proj2['id']}/places/{place['id']}", headers=auth)
    assert resp.status_code == 404


# ── update place ──────────────────────────────────────────────────────────────

async def test_update_place_notes(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    place = await add_place(client, auth, proj["id"], 27992)

    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        resp = await client.patch(
            f"/projects/{proj['id']}/places/{place['id']}",
            json={"notes": "Amazing pointillist work!"},
            headers=auth,
        )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Amazing pointillist work!"
    assert resp.json()["is_visited"] is False


async def test_mark_place_visited(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    place = await add_place(client, auth, proj["id"], 27992)

    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        resp = await client.patch(
            f"/projects/{proj['id']}/places/{place['id']}",
            json={"is_visited": True},
            headers=auth,
        )
    assert resp.status_code == 200
    assert resp.json()["is_visited"] is True


async def test_update_place_not_found(client: AsyncClient, auth: dict):
    proj = await make_project(client, auth)
    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        resp = await client.patch(
            f"/projects/{proj['id']}/places/9999",
            json={"notes": "x"},
            headers=auth,
        )
    assert resp.status_code == 404


# ── business logic ────────────────────────────────────────────────────────────

async def test_project_becomes_completed_when_all_visited(client: AsyncClient, auth: dict):
    with patch(PATCH_PROJECTS, side_effect=mock_get_artwork):
        proj_resp = await client.post(
            "/projects",
            json={"name": "Complete Me", "places": [{"external_id": 27992}, {"external_id": 16487}]},
            headers=auth,
        )
    proj = proj_resp.json()
    place_ids = [p["id"] for p in proj["places"]]

    # After first visited — still active
    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        await client.patch(
            f"/projects/{proj['id']}/places/{place_ids[0]}",
            json={"is_visited": True},
            headers=auth,
        )
    status_resp = await client.get(f"/projects/{proj['id']}", headers=auth)
    assert status_resp.json()["status"] == "active"

    # After second visited — completed
    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        await client.patch(
            f"/projects/{proj['id']}/places/{place_ids[1]}",
            json={"is_visited": True},
            headers=auth,
        )
    status_resp = await client.get(f"/projects/{proj['id']}", headers=auth)
    assert status_resp.json()["status"] == "completed"


async def test_project_stays_active_with_unvisited_places(client: AsyncClient, auth: dict):
    with patch(PATCH_PROJECTS, side_effect=mock_get_artwork):
        proj_resp = await client.post(
            "/projects",
            json={"name": "Stay Active", "places": [{"external_id": 27992}, {"external_id": 16487}]},
            headers=auth,
        )
    proj = proj_resp.json()
    first_place_id = proj["places"][0]["id"]

    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        await client.patch(
            f"/projects/{proj['id']}/places/{first_place_id}",
            json={"is_visited": True},
            headers=auth,
        )

    status_resp = await client.get(f"/projects/{proj['id']}", headers=auth)
    assert status_resp.json()["status"] == "active"
