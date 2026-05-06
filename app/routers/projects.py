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
    PaginatedProjects,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.artic_api import get_artwork, _image_url

router = APIRouter(prefix="/projects", tags=["Projects"])


async def _fetch_project_or_404(project_id: int, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).options(selectinload(Project.places)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _sync_project_status(project: Project, db: AsyncSession) -> None:
    if project.places and all(p.is_visited for p in project.places):
        project.status = ProjectStatus.completed
    else:
        project.status = ProjectStatus.active
    await db.commit()
    await db.refresh(project)


@router.get("", response_model=PaginatedProjects, summary="List travel projects")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Optional[ProjectStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    query = select(Project).options(selectinload(Project.places))
    if status_filter:
        query = query.where(Project.status == status_filter)

    count_q = select(func.count()).select_from(Project)
    if status_filter:
        count_q = count_q.where(Project.status == status_filter)
    total = (await db.execute(count_q)).scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Project.created_at.desc())
    projects = (await db.execute(query)).scalars().all()

    return PaginatedProjects(
        items=projects,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, summary="Create a travel project")
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    places_data = payload.places or []

    if len(places_data) > 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A project can contain at most 10 places",
        )

    project = Project(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
    )
    db.add(project)
    await db.flush()

    seen_external_ids: set[int] = set()
    for place_import in places_data:
        if place_import.external_id in seen_external_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Duplicate external_id {place_import.external_id} in request",
            )
        seen_external_ids.add(place_import.external_id)

        artwork = await get_artwork(place_import.external_id)
        if not artwork:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Artwork with id={place_import.external_id} not found in Art Institute API",
            )

        db.add(
            Place(
                project_id=project.id,
                external_id=artwork.id,
                title=artwork.title,
                image_url=_image_url(artwork.image_id),
            )
        )

    await db.commit()
    await db.refresh(project)

    result = await db.execute(
        select(Project).options(selectinload(Project.places)).where(Project.id == project.id)
    )
    return result.scalar_one()


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get a single travel project")
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    return await _fetch_project_or_404(project_id, db)


@router.patch("/{project_id}", response_model=ProjectResponse, summary="Update project information")
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await _fetch_project_or_404(project_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a travel project")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await _fetch_project_or_404(project_id, db)

    if any(p.is_visited for p in project.places):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a project that has visited places",
        )

    await db.delete(project)
    await db.commit()
