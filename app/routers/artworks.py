from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import get_current_user
from app.schemas import ArticArtwork
from app.services.artic_api import get_artwork, search_artworks
from fastapi import Depends

router = APIRouter(prefix="/artworks", tags=["Artworks (Art Institute of Chicago)"])


@router.get("/search", summary="Search artworks from Art Institute of Chicago")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    _: str = Depends(get_current_user),
):
    return await search_artworks(q, page=page, limit=limit)


@router.get("/{artwork_id}", response_model=ArticArtwork, summary="Get a single artwork by ID")
async def get_single_artwork(
    artwork_id: int,
    _: str = Depends(get_current_user),
):
    artwork = await get_artwork(artwork_id)
    if not artwork:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artwork not found")
    return artwork
