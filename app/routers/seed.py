from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Place, Project
from app.services.artic_api import _image_url, search_artworks

router = APIRouter(prefix="/seed", tags=["Seed"])

# Each entry: project metadata + search query + how many artworks to pull
SEED_PLANS = [
    {
        "name": "Impressionism Tour",
        "description": "The finest impressionist works in Chicago's collection",
        "start_date": date(2025, 7, 1),
        "query": "impressionism monet",
        "count": 4,
    },
    {
        "name": "American Masterpieces",
        "description": "Iconic American paintings across the centuries",
        "start_date": date(2025, 9, 15),
        "query": "american painting hopper",
        "count": 3,
    },
    {
        "name": "Modern & Abstract",
        "description": "Bold explorations of form, color and abstraction",
        "start_date": None,
        "query": "abstract modern picasso",
        "count": 3,
    },
]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Seed the database with sample projects and real artworks",
    description=(
        "Creates sample travel projects and populates them with artworks fetched "
        "from the Art Institute of Chicago API. Safe to call multiple times — "
        "each call creates a fresh set of projects."
    ),
)
async def seed(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    created_projects = []

    for plan in SEED_PLANS:
        result = await search_artworks(plan["query"], page=1, limit=plan["count"] + 5)
        artworks = result.get("data", [])

        if not artworks:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Art Institute API returned no results for query '{plan['query']}'",
            )

        project = Project(
            name=plan["name"],
            description=plan["description"],
            start_date=plan["start_date"],
        )
        db.add(project)
        await db.flush()

        seen: set[int] = set()
        added = 0
        for artwork in artworks:
            if added >= plan["count"]:
                break
            ext_id: int = artwork.get("id")
            if not ext_id or ext_id in seen:
                continue
            seen.add(ext_id)

            title = artwork.get("title") or "Untitled"
            image_id = artwork.get("image_id")

            db.add(
                Place(
                    project_id=project.id,
                    external_id=ext_id,
                    title=title,
                    image_url=_image_url(image_id),
                )
            )
            added += 1

        await db.flush()
        await db.refresh(project)
        created_projects.append({"id": project.id, "name": project.name, "places_added": added})

    await db.commit()

    total_places = sum(p["places_added"] for p in created_projects)
    return {
        "message": f"Seeded {len(created_projects)} projects with {total_places} places total",
        "projects": created_projects,
    }
