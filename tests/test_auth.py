import pytest
from httpx import AsyncClient


async def test_get_token_success(client: AsyncClient):
    resp = await client.post(
        "/auth/token",
        data={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_get_token_wrong_password(client: AsyncClient):
    resp = await client.post(
        "/auth/token",
        data={"username": "admin", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


async def test_get_token_unknown_user(client: AsyncClient):
    resp = await client.post(
        "/auth/token",
        data={"username": "nobody", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


async def test_protected_endpoint_without_token(client: AsyncClient):
    resp = await client.get("/projects")
    assert resp.status_code == 401


async def test_protected_endpoint_with_invalid_token(client: AsyncClient):
    resp = await client.get("/projects", headers={"Authorization": "Bearer bad.token.here"})
    assert resp.status_code == 401


async def test_protected_endpoint_with_valid_token(client: AsyncClient, auth: dict):
    resp = await client.get("/projects", headers=auth)
    assert resp.status_code == 200


async def test_register_new_user(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"username": "newuser", "password": "secret123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "newuser"
    assert body["is_active"] is True
    assert "id" in body


async def test_register_duplicate_username(client: AsyncClient):
    await client.post("/auth/register", json={"username": "dupuser", "password": "pass123"})
    resp = await client.post("/auth/register", json={"username": "dupuser", "password": "pass123"})
    assert resp.status_code == 409


async def test_register_short_password(client: AsyncClient):
    resp = await client.post("/auth/register", json={"username": "user2", "password": "123"})
    assert resp.status_code == 422


async def test_register_short_username(client: AsyncClient):
    resp = await client.post("/auth/register", json={"username": "ab", "password": "pass123"})
    assert resp.status_code == 422


async def test_registered_user_can_login(client: AsyncClient):
    await client.post("/auth/register", json={"username": "logintest", "password": "mypassword"})
    resp = await client.post(
        "/auth/token",
        data={"username": "logintest", "password": "mypassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
