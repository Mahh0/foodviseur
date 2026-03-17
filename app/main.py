import os
import logging
import threading
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import init_db, DATABASE_URL
from app.routers import meals, goals, food_search

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))

app = FastAPI(title="FoodViseur", version="1.0.0", docs_url="/api/docs")


@app.on_event("startup")
def startup():
    init_db()
    # Import OFF local en arrière-plan pour ne pas bloquer le démarrage
    if os.getenv("OFF_LOCAL_ENABLED", "false").lower() == "true":
        db_path = DATABASE_URL.replace("sqlite:////", "/").replace("sqlite:///", "")
        def _run():
            from app.off_importer import run_if_needed
            run_if_needed(db_path)
        t = threading.Thread(target=_run, daemon=True)
        t.start()


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
