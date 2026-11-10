"""FastAPI application entry point. Run with: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import places, plan, profile, trips
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if get_settings().seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title="Commute Planner API",
    description="Plans a week of trips: which transport mode, when to leave, and when plan B expires.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

for router in (places.router, trips.router, profile.router, plan.router):
    app.include_router(router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str | bool]:
    return {"status": "ok", "ai_advice": bool(get_settings().anthropic_api_key)}


def _serve_frontend(application: FastAPI) -> None:
    """Single-container deployment: the API also hands out the built React app."""
    static_dir = get_settings().static_dir
    application.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @application.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        # Client-side routes such as /week are all served by the same page.
        return FileResponse(static_dir / "index.html")


if get_settings().serve_frontend:
    _serve_frontend(app)
