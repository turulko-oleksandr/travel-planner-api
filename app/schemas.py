from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models import ProjectStatus


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Places ────────────────────────────────────────────────────────────────────

class PlaceImport(BaseModel):
    external_id: int = Field(..., description="Artwork ID from Art Institute of Chicago API")


class PlaceCreate(BaseModel):
    external_id: int = Field(..., description="Artwork ID from Art Institute of Chicago API")


class PlaceUpdate(BaseModel):
    notes: Optional[str] = None
    is_visited: Optional[bool] = None

    @field_validator("notes")
    @classmethod
    def notes_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            return None
        return v


class PlaceResponse(BaseModel):
    id: int
    project_id: int
    external_id: int
    title: str
    image_url: Optional[str]
    notes: Optional[str]
    is_visited: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedPlaces(BaseModel):
    items: list[PlaceResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[date] = None
    places: Optional[list[PlaceImport]] = Field(
        default=None,
        description="Optional list of places to import on project creation (max 10)",
    )

    @field_validator("places")
    @classmethod
    def validate_places_count(cls, v: Optional[list[PlaceImport]]) -> Optional[list[PlaceImport]]:
        if v is not None and len(v) > 10:
            raise ValueError("A project can contain at most 10 places")
        return v


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[date] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    start_date: Optional[date]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    places: list[PlaceResponse] = []

    model_config = {"from_attributes": True}


class PaginatedProjects(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Artic API (external) ──────────────────────────────────────────────────────

class ArticArtwork(BaseModel):
    id: int
    title: str
    image_id: Optional[str] = None
