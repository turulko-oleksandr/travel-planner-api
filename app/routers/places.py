from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Place, Project, ProjectStatus
from app.schemas import (
    PaginatedPlaces,
    PlaceCreate,
    PlaceResponse,
    PlaceUpdate,
)
from app.services.artic_api import _image_url, get_artwork

router = APIRouter(prefix="/projects/{project_id}/places", tags=["Places"])

MAX_PLACES = 10


async def _fetch_project_or_404(project_id: int, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).options(selectinload(Project.places)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _fetch_place_or_404(place_id: int, project_id: int, db: AsyncSession) -> Place:
    result = await db.execute(
        select(Place).where(Place.id == place_id, Place.project_id == project_id)
    )
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found")
    return place


async def _sync_project_status(project: Project, db: AsyncSession) -> None:
    if project.places and all(p.is_visited for p in project.places):
        project.status = ProjectStatus.completed
    else:
        project.status = ProjectStatus.active


@router.get("", response_model=PaginatedPlaces, summary="List all places for a project")
async def list_places(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    visited: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    await _fetch_project_or_404(project_id, db)

    query = select(Place).where(Place.project_id == project_id)
    count_q = select(func.count()).select_from(Place).where(Place.project_id == project_id)

    if visited is not None:
        query = query.where(Place.is_visited == visited)
        count_q = count_q.where(Place.is_visited == visited)

    total = (await db.execute(count_q)).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Place.created_at.asc())
    places = (await db.execute(query)).scalars().all()

    return PaginatedPlaces(
        items=places,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=PlaceResponse, status_code=status.HTTP_201_CREATED, summary="Add a place to a project")
async def add_place(
    project_id: int,
    payload: PlaceCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await _fetch_project_or_404(project_id, db)

    if len(project.places) >= MAX_PLACES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Project already has the maximum of {MAX_PLACES} places",
        )

    duplicate = any(p.external_id == payload.external_id for p in project.places)
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Place with external_id={payload.external_id} already exists in this project",
        )

    artwork = await get_artwork(payload.external_id)
    if not artwork:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Artwork with id={payload.external_id} not found in Art Institute API",
        )

    place = Place(
        project_id=project.id,
        external_id=artwork.id,
        title=artwork.title,
        image_url=_image_url(artwork.image_id),
    )
    db.add(place)
    await db.commit()
    await db.refresh(place)
    return place


@router.get("/{place_id}", response_model=PlaceResponse, summary="Get a single place within a project")
async def get_place(
    project_id: int,
    place_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    await _fetch_project_or_404(project_id, db)
    return await _fetch_place_or_404(place_id, project_id, db)


@router.patch("/{place_id}", response_model=PlaceResponse, summary="Update notes or visited status of a place")
async def update_place(
    project_id: int,
    place_id: int,
    payload: PlaceUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await _fetch_project_or_404(project_id, db)
    place = await _fetch_place_or_404(place_id, project_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(place, field, value)

    await db.flush()

    # Reload places to compute status
    result = await db.execute(
        select(Project).options(selectinload(Project.places)).where(Project.id == project_id)
    )
    project = result.scalar_one()
    await _sync_project_status(project, db)

    await db.commit()
    await db.refresh(place)
    return place
