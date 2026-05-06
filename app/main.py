from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import AsyncSessionLocal, init_db
from app.routers import auth, projects, places, artworks, seed
from app.services.auth import create_user, get_user


async def _seed_default_admin() -> None:
    async with AsyncSessionLocal() as db:
        if not await get_user(db, "admin"):
            await create_user(db, "admin", "admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _seed_default_admin()
    yield


app = FastAPI(
    title="Travel Planner API",
    description=(
        "A CRUD application for managing travel projects and places. "
        "Places are validated against the Art Institute of Chicago public API."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(places.router)
app.include_router(artworks.router)
app.include_router(seed.router)


@app.get("/", tags=["Health"])
async def health():
    return {"status": "ok", "message": "Travel Planner API is running"}
