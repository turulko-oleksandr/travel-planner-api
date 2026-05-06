from typing import Optional

import httpx
from cachetools import TTLCache

from app.core.config import settings
from app.schemas import ArticArtwork

_cache: TTLCache = TTLCache(maxsize=1024, ttl=settings.CACHE_TTL_SECONDS)

IIIF_BASE = "https://www.artic.edu/iiif/2"


def _image_url(image_id: Optional[str]) -> Optional[str]:
    if not image_id:
        return None
    return f"{IIIF_BASE}/{image_id}/full/843,/0/default.jpg"


async def get_artwork(artwork_id: int) -> Optional[ArticArtwork]:
    if artwork_id in _cache:
        return _cache[artwork_id]

    url = f"{settings.ARTIC_API_BASE_URL}/artworks/{artwork_id}"
    params = {"fields": "id,title,image_id"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.RequestError:
            return None

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        return None

    payload = resp.json().get("data")
    if not payload:
        return None

    artwork = ArticArtwork(
        id=payload["id"],
        title=payload.get("title", "Untitled"),
        image_id=payload.get("image_id"),
    )
    _cache[artwork_id] = artwork
    return artwork


async def search_artworks(query: str, page: int = 1, limit: int = 10) -> dict:
    cache_key = f"search:{query}:{page}:{limit}"
    if cache_key in _cache:
        return _cache[cache_key]

    url = f"{settings.ARTIC_API_BASE_URL}/artworks/search"
    params = {
        "q": query,
        "page": page,
        "limit": limit,
        "fields": "id,title,image_id",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.RequestError:
            return {"data": [], "pagination": {}}

    if resp.status_code != 200:
        return {"data": [], "pagination": {}}

    result = resp.json()
    _cache[cache_key] = result
    return result
