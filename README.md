# Travel Planner API

A RESTful API for managing travel projects and places, built with **FastAPI**, **SQLAlchemy (async)**, and **SQLite**. Places are validated and imported from the [Art Institute of Chicago public API](https://api.artic.edu/docs/).

## Features

- Full **CRUD** for travel projects and places
- **Import places** from the Art Institute of Chicago API by artwork ID
- **Business logic**: max 10 places per project; no duplicate places; project auto-completes when all places are visited; cannot delete a project with visited places
- **JWT authentication** (Bearer token)
- **Pagination & filtering** on list endpoints
- **TTL caching** for Art Institute API responses (default 5 min)
- **OpenAPI / Swagger UI** at `/docs`
- **Docker** support

---

## Quick Start

### Option 1 — Docker Compose (recommended)

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

### Option 2 — Local (Python 3.12+)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) copy and edit environment variables
cp .env.example .env

# 4. Run the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./travel_planner.db` | SQLAlchemy async database URL |
| `ARTIC_API_BASE_URL` | `https://api.artic.edu/api/v1` | Art Institute of Chicago base URL |
| `CACHE_TTL_SECONDS` | `300` | How long to cache Art Institute responses |
| `SECRET_KEY` | `change-me-in-production` | JWT signing secret |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token TTL in minutes |

---

## Authentication

The API uses **JWT Bearer tokens**. A default user is pre-created:

| Username | Password |
|---|---|
| `admin` | `admin123` |

Obtain a token:

```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

Include the token in subsequent requests:

```
Authorization: Bearer <access_token>
```

---

## API Endpoints

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/` | Health check |

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/token` | Obtain JWT access token |

### Artworks (Art Institute of Chicago proxy)
| Method | Path | Description |
|---|---|---|
| GET | `/artworks/search?q=monet` | Search artworks |
| GET | `/artworks/{id}` | Get artwork by ID |

### Projects
| Method | Path | Description |
|---|---|---|
| GET | `/projects` | List projects (paginated, filterable by `status`) |
| POST | `/projects` | Create project (optionally with places) |
| GET | `/projects/{id}` | Get single project |
| PATCH | `/projects/{id}` | Update project info |
| DELETE | `/projects/{id}` | Delete project (blocked if any place is visited) |

### Places
| Method | Path | Description |
|---|---|---|
| GET | `/projects/{id}/places` | List places (paginated, filterable by `visited`) |
| POST | `/projects/{id}/places` | Add a place to project |
| GET | `/projects/{id}/places/{place_id}` | Get single place |
| PATCH | `/projects/{id}/places/{place_id}` | Update notes / mark visited |

Interactive documentation: **`http://localhost:8000/docs`**

---

## Postman Collection

Import `postman_collection.json` into Postman.

The collection uses collection variables:
- `base_url` — defaults to `http://localhost:8000`
- `token` — auto-populated by the **Get Token** request

**Recommended flow:**
1. Run **Auth → Get Token** (saves token automatically)
2. Search artworks to find valid `external_id` values — e.g. **Artworks → Search Artworks** (`q=monet`)
3. **Create Project (with places)** using IDs from step 2
4. Explore place endpoints

---

## Project Structure

```
.
├── app/
│   ├── core/
│   │   └── config.py          # Settings via pydantic-settings
│   ├── routers/
│   │   ├── auth.py            # JWT token endpoint
│   │   ├── projects.py        # Project CRUD
│   │   ├── places.py          # Place CRUD (nested under projects)
│   │   └── artworks.py        # Art Institute proxy + search
│   ├── services/
│   │   ├── artic_api.py       # Art Institute API client + TTL cache
│   │   └── auth.py            # Password hashing, JWT
│   ├── database.py            # Async SQLAlchemy engine + session
│   ├── dependencies.py        # FastAPI dependency: get_current_user
│   ├── models.py              # SQLAlchemy ORM models
│   ├── schemas.py             # Pydantic request/response schemas
│   └── main.py                # FastAPI app, middleware, router wiring
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── postman_collection.json
```

---

## Business Rules Summary

- A project can hold **1–10 places** (enforced on creation and when adding)
- The same artwork (by `external_id`) **cannot be added twice** to the same project
- A place must **exist in the Art Institute API** before it can be added
- A project **cannot be deleted** if any of its places are marked as visited
- When **all places** in a project are marked as visited, the project status changes to `completed` automatically
