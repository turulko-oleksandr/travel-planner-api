from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.conftest import mock_get_artwork

PATCH_PROJECTS = "app.routers.projects.get_artwork"
PATCH_PLACES = "app.routers.places.get_artwork"


# ── helpers ───────────────────────────────────────────────────────────────────

async def create_project(client: AsyncClient, auth: dict, payload: dict | None = None) -> dict:
    payload = payload or {"name": "Test Project"}
    resp = await client.post("/projects", json=payload, headers=auth)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_projects_empty(client: AsyncClient, auth: dict):
    resp = await client.get("/projects", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_list_projects_pagination_shape(client: AsyncClient, auth: dict):
    for i in range(3):
        await create_project(client, auth, {"name": f"Project {i}"})

    resp = await client.get("/projects?page=1&page_size=2", headers=auth)
    body = resp.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2


async def test_list_projects_filter_by_status(client: AsyncClient, auth: dict):
    await create_project(client, auth, {"name": "Active"})

    resp = await client.get("/projects?status=active", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.get("/projects?status=completed", headers=auth)
    assert resp.json()["total"] == 0


# ── create ────────────────────────────────────────────────────────────────────

async def test_create_project_minimal(client: AsyncClient, auth: dict):
    resp = await client.post("/projects", json={"name": "My Trip"}, headers=auth)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Trip"
    assert body["status"] == "active"
    assert body["places"] == []


async def test_create_project_full_fields(client: AsyncClient, auth: dict):
    payload = {
        "name": "Art Tour",
        "description": "Chicago museums",
        "start_date": "2025-09-01",
    }
    resp = await client.post("/projects", json=payload, headers=auth)
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] == "Chicago museums"
    assert body["start_date"] == "2025-09-01"


async def test_create_project_with_places(client: AsyncClient, auth: dict):
    payload = {
        "name": "With Places",
        "places": [{"external_id": 27992}, {"external_id": 16487}],
    }
    with patch(PATCH_PROJECTS, side_effect=mock_get_artwork):
        resp = await client.post("/projects", json=payload, headers=auth)
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["places"]) == 2
    titles = {p["title"] for p in body["places"]}
    assert "A Sunday on La Grande Jatte" in titles


async def test_create_project_invalid_artwork_id(client: AsyncClient, auth: dict):
    payload = {"name": "Bad Place", "places": [{"external_id": 999999}]}
    with patch(PATCH_PROJECTS, return_value=None):
        resp = await client.post("/projects", json=payload, headers=auth)
    assert resp.status_code == 422


async def test_create_project_duplicate_places_in_request(client: AsyncClient, auth: dict):
    payload = {
        "name": "Dupe Test",
        "places": [{"external_id": 27992}, {"external_id": 27992}],
    }
    with patch(PATCH_PROJECTS, side_effect=mock_get_artwork):
        resp = await client.post("/projects", json=payload, headers=auth)
    assert resp.status_code == 422


async def test_create_project_too_many_places(client: AsyncClient, auth: dict):
    ids = [27992, 16487, 14620, 20684, 28560, 80607, 111628, 100472, 24645, 60755, 11272]
    payload = {"name": "Too Many", "places": [{"external_id": i} for i in ids]}
    resp = await client.post("/projects", json=payload, headers=auth)
    assert resp.status_code == 422


async def test_create_project_missing_name(client: AsyncClient, auth: dict):
    resp = await client.post("/projects", json={"description": "no name"}, headers=auth)
    assert resp.status_code == 422


# ── get ───────────────────────────────────────────────────────────────────────

async def test_get_project(client: AsyncClient, auth: dict):
    created = await create_project(client, auth)
    resp = await client.get(f"/projects/{created['id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_project_not_found(client: AsyncClient, auth: dict):
    resp = await client.get("/projects/9999", headers=auth)
    assert resp.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────

async def test_update_project_name(client: AsyncClient, auth: dict):
    created = await create_project(client, auth)
    resp = await client.patch(
        f"/projects/{created['id']}",
        json={"name": "Updated Name"},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


async def test_update_project_partial(client: AsyncClient, auth: dict):
    created = await create_project(client, auth, {"name": "Original", "description": "desc"})
    resp = await client.patch(
        f"/projects/{created['id']}",
        json={"description": "new desc"},
        headers=auth,
    )
    body = resp.json()
    assert body["name"] == "Original"
    assert body["description"] == "new desc"


async def test_update_project_not_found(client: AsyncClient, auth: dict):
    resp = await client.patch("/projects/9999", json={"name": "X"}, headers=auth)
    assert resp.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

async def test_delete_project_success(client: AsyncClient, auth: dict):
    created = await create_project(client, auth)
    resp = await client.delete(f"/projects/{created['id']}", headers=auth)
    assert resp.status_code == 204

    resp = await client.get(f"/projects/{created['id']}", headers=auth)
    assert resp.status_code == 404


async def test_delete_project_not_found(client: AsyncClient, auth: dict):
    resp = await client.delete("/projects/9999", headers=auth)
    assert resp.status_code == 404


async def test_delete_project_blocked_when_place_visited(client: AsyncClient, auth: dict):
    with patch(PATCH_PROJECTS, side_effect=mock_get_artwork):
        proj = await create_project(
            client, auth, {"name": "Visited", "places": [{"external_id": 27992}]}
        )

    place_id = proj["places"][0]["id"]
    with patch(PATCH_PLACES, side_effect=mock_get_artwork):
        await client.patch(
            f"/projects/{proj['id']}/places/{place_id}",
            json={"is_visited": True},
            headers=auth,
        )

    resp = await client.delete(f"/projects/{proj['id']}", headers=auth)
    assert resp.status_code == 409
