from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.schemas import ArticArtwork
from app.services.auth import hash_password

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Reusable mock artworks — returned by patched get_artwork()
MOCK_ARTWORKS: dict[int, ArticArtwork] = {
    27992: ArticArtwork(id=27992, title="A Sunday on La Grande Jatte", image_id="img-001"),
    16487: ArticArtwork(id=16487, title="The Bay of Marseille", image_id="img-002"),
    14620: ArticArtwork(id=14620, title="Nighthawks", image_id="img-003"),
    20684: ArticArtwork(id=20684, title="American Gothic", image_id="img-004"),
    28560: ArticArtwork(id=28560, title="Water Lilies", image_id="img-005"),
    80607: ArticArtwork(id=80607, title="The Old Guitarist", image_id="img-006"),
    111628: ArticArtwork(id=111628, title="Starry Night Study", image_id="img-007"),
    100472: ArticArtwork(id=100472, title="Girl with a Pearl Earring Study", image_id="img-008"),
    24645: ArticArtwork(id=24645, title="The Bedroom", image_id="img-009"),
    60755: ArticArtwork(id=60755, title="Bathers at Asnieres", image_id="img-010"),
    11272: ArticArtwork(id=11272, title="Extra Artwork", image_id="img-011"),
}


async def mock_get_artwork(artwork_id: int) -> ArticArtwork | None:
    return MOCK_ARTWORKS.get(artwork_id)


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    # Seed admin user into the test DB
    async with TestSession() as session:
        session.add(User(username="admin", hashed_password=hash_password("admin123")))
        await session.commit()

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def token(client: AsyncClient) -> str:
    resp = await client.post(
        "/auth/token",
        data={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
