import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import init_db
from app.routers import meals, goals, food_search

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))

app = FastAPI(title="FoodViseur", version="1.0.0", docs_url="/api/docs")


@app.on_event("startup")
def startup():
    init_db()


# API routers
app.include_router(meals.router)
app.include_router(goals.router)
app.include_router(food_search.router)

# Static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/manifest.json")
def manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"))


@app.get("/service-worker.js")
def service_worker():
    return FileResponse(
        os.path.join(STATIC_DIR, "service-worker.js"),
        media_type="application/javascript",
    )


@app.get("/{full_path:path}")
def spa(full_path: str):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
