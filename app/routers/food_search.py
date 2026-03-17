import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import httpx
import logging
from app.database import get_db
from app import crud, schemas
from app.models import CiqualFood, OFFFood

OFF_LOCAL_ENABLED = os.getenv("OFF_LOCAL_ENABLED", "false").lower() == "true"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/food", tags=["food"])

OFF_BASE       = "https://world.openfoodfacts.org"
OFF_USER_AGENT = os.getenv("OFF_USER_AGENT", "FoodViseur/1.0 (self-hosted)")
HEADERS        = {"User-Agent": OFF_USER_AGENT}
TIMEOUT        = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
CIQUAL_MIN_RESULTS = 3


# ─── CIQUAL ─────────────────────────────────────────────────────────────────

def search_ciqual(db: Session, q: str, limit: int = 15) -> list[schemas.FoodItem]:
    """
    Recherche CIQUAL avec ranking :
    1. Correspondance exacte en début de mot (pomme → Pomme Golden, Compote de pommes)
    2. Correspondance partielle (%pomme%)
    """
    q_lower = q.lower().strip()
    pattern_start = f"{q_lower}%"   # commence par le terme
    pattern_any   = f"%{q_lower}%"  # contient le terme

    # Résultats prioritaires : nom commence par q
    priority = (
        db.query(CiqualFood)
        .filter(func.lower(CiqualFood.name_fr).like(pattern_start))
        .limit(limit)
        .all()
    )

    # Compléter avec les autres si pas assez
    if len(priority) < limit:
        priority_ids = {r.id for r in priority}
        others = (
            db.query(CiqualFood)
            .filter(
                func.lower(CiqualFood.name_fr).like(pattern_any),
                ~CiqualFood.id.in_(priority_ids)
            )
            .limit(limit - len(priority))
            .all()
        )
        rows = priority + others
    else:
        rows = priority

    return [
        schemas.FoodItem(
            id=row.id,
            name=row.name_fr,
            brand=None,
            calories_100g=row.calories_100g,
            proteins_100g=row.proteins_100g,
            carbs_100g=row.carbs_100g,
            fats_100g=row.fats_100g,
            fibers_100g=row.fibers_100g,
        )
        for row in rows
    ]


def ciqual_available(db: Session) -> bool:
    try:
        return db.query(CiqualFood).limit(1).count() > 0
    except Exception:
        return False


# ─── OFF ────────────────────────────────────────────────────────────────────


def search_off_local(db: Session, q: str, limit: int = 15) -> list[schemas.FoodItem]:
    """Recherche dans la base OFF locale (si OFF_LOCAL_ENABLED=true)."""
    if not OFF_LOCAL_ENABLED:
        return []
    q_lower = q.lower().strip()
    pattern_start = f"{q_lower}%"
    pattern_any   = f"%{q_lower}%"

    priority = (
        db.query(OFFFood)
        .filter(func.lower(OFFFood.name).like(pattern_start))
        .limit(limit)
        .all()
    )
    if len(priority) < limit:
        priority_ids = {r.id for r in priority}
        others = (
            db.query(OFFFood)
            .filter(
                func.lower(OFFFood.name).like(pattern_any),
                ~OFFFood.id.in_(priority_ids)
            )
            .limit(limit - len(priority))
            .all()
        )
        rows = priority + others
    else:
        rows = priority

    return [
        schemas.FoodItem(
            barcode=row.barcode,
            name=row.name,
            brand=row.brand,
            calories_100g=row.calories_100g,
            proteins_100g=row.proteins_100g,
            carbs_100g=row.carbs_100g,
            fats_100g=row.fats_100g,
            fibers_100g=row.fibers_100g,
            image_url=row.image_url,
        )
        for row in rows
    ]


def parse_off_product(product: dict) -> schemas.FoodItem:
    nutriments = product.get("nutriments", {})
    calories = (
        nutriments.get("energy-kcal_100g")
        or nutriments.get("energy-kcal")
        or (float(nutriments.get("energy_100g", 0) or 0) / 4.184)
    )
    name = (
        product.get("product_name_fr")
        or product.get("product_name")
        or product.get("abbreviated_product_name")
        or ""
    ).strip()
    brands_raw = product.get("brands") or ""
    brand = brands_raw.split(",")[0].strip() or None

    return schemas.FoodItem(
        barcode=product.get("code") or product.get("id") or None,
        off_id=product.get("_id") or product.get("id") or None,
        name=name or "Produit inconnu",
        brand=brand,
        calories_100g=round(float(calories or 0), 1),
        proteins_100g=round(float(nutriments.get("proteins_100g") or 0), 1),
        carbs_100g=round(float(nutriments.get("carbohydrates_100g") or 0), 1),
        fats_100g=round(float(nutriments.get("fat_100g") or 0), 1),
        fibers_100g=round(float(nutriments.get("fiber_100g") or 0), 1),
        image_url=product.get("image_front_small_url") or product.get("image_url") or None,
    )


async def search_off(q: str, db: Session, limit: int = 12) -> list[schemas.FoodItem]:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{OFF_BASE}/cgi/search.pl",
                params={
                    "search_terms": q,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": limit,
                    "lc": "fr",
                    "cc": "fr",
                    "fields": "id,code,product_name,product_name_fr,abbreviated_product_name,brands,nutriments,image_front_small_url",
                },
            )
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning(f"OFF search error for '{q}': {e}")
        return []

    if resp.status_code != 200:
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    results = []
    for p in data.get("products", []):
        try:
            food = parse_off_product(p)
            if food.name and food.name != "Produit inconnu":
                try:
                    crud.cache_food(db, food)
                except Exception:
                    pass
                results.append(food)
        except Exception as e:
            logger.debug(f"Skipping OFF product: {e}")
    return results


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/recent", response_model=list[schemas.RecentFoodItem])
def get_recent_foods(db: Session = Depends(get_db)):
    return crud.get_recent_foods(db)


@router.get("/custom", response_model=list[schemas.FoodItem])
def get_custom_foods(db: Session = Depends(get_db)):
    """Liste les aliments saisis manuellement."""
    from app.models import FoodCache
    rows = (
        db.query(FoodCache)
        .filter(FoodCache.is_custom == True)
        .order_by(FoodCache.cached_at.desc())
        .all()
    )
    return [schemas.FoodItem.model_validate(r) for r in rows]


@router.post("/custom", response_model=schemas.FoodItem)
def create_custom_food(food: schemas.FoodItem, db: Session = Depends(get_db)):
    """Persiste un aliment saisi manuellement."""
    saved = crud.save_custom_food(db, food)
    return schemas.FoodItem.model_validate(saved)


@router.delete("/custom/{food_id}")
def delete_custom_food(food_id: int, db: Session = Depends(get_db)):
    """Supprime un aliment custom."""
    success = crud.delete_custom_food(db, food_id)
    if not success:
        raise HTTPException(status_code=404, detail="Aliment non trouvé ou non supprimable")
    return {"deleted": food_id}


@router.get("/barcode/{barcode}", response_model=schemas.FoodItem)
async def get_by_barcode(barcode: str, db: Session = Depends(get_db)):
    # 1. food_cache (produits déjà scannés)
    cached = crud.get_food_by_barcode(db, barcode)
    if cached:
        return cached

    # 2. Base OFF locale si activée
    if OFF_LOCAL_ENABLED:
        off_local = db.query(OFFFood).filter(OFFFood.barcode == barcode).first()
        if off_local:
            return schemas.FoodItem(
                barcode=off_local.barcode,
                name=off_local.name,
                brand=off_local.brand,
                calories_100g=off_local.calories_100g,
                proteins_100g=off_local.proteins_100g,
                carbs_100g=off_local.carbs_100g,
                fats_100g=off_local.fats_100g,
                fibers_100g=off_local.fibers_100g,
                image_url=off_local.image_url,
            )

    # Si OFF local activé, ne pas appeler l'API — produit inconnu
    if OFF_LOCAL_ENABLED:
        raise HTTPException(status_code=404, detail="Produit non trouvé dans la base locale")

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
            resp = await client.get(f"{OFF_BASE}/api/v0/product/{barcode}.json")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Open Food Facts timeout — réessayez")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Erreur réseau : {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Open Food Facts indisponible")

    data = resp.json()
    if data.get("status") != 1:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    food = parse_off_product(data["product"])
    food.barcode = barcode
    cached = crud.cache_food(db, food)
    return cached


@router.get("/search", response_model=list[schemas.FoodItem])
async def search_food(q: str, source: str = "auto", db: Session = Depends(get_db)):
    """
    Recherche hybride CIQUAL + OFF.
    - source=auto   : CIQUAL d'abord, complète avec OFF si < 3 résultats
    - source=ciqual : CIQUAL uniquement
    - source=off    : OFF uniquement
    """
    if len(q) < 2:
        return []

    if source == "off":
        results = await search_off(q, db)
        if not results:
            raise HTTPException(status_code=504, detail="Open Food Facts indisponible ou timeout")
        return results[:15]

    if source == "ciqual":
        return search_ciqual(db, q, limit=15)

    # Auto : CIQUAL d'abord
    ciqual_results = search_ciqual(db, q, limit=15)

    # Compléter avec OFF local si disponible
    if OFF_LOCAL_ENABLED:
        if len(ciqual_results) < CIQUAL_MIN_RESULTS:
            logger.info(f"[search] CIQUAL: {len(ciqual_results)} résultats pour '{q}', complétion OFF local")
        off_local = search_off_local(db, q, limit=15 - len(ciqual_results))
        seen_names = {r.name.lower() for r in ciqual_results}
        for r in off_local:
            if r.name.lower() not in seen_names:
                ciqual_results.append(r)
                seen_names.add(r.name.lower())
        # En mode local, on ne complète JAMAIS avec l'API OFF automatiquement
        # L'utilisateur doit cliquer explicitement sur "Rechercher sur OFF"
        return ciqual_results[:15]

    # Sans OFF local : compléter avec l'API OFF uniquement si source='off_auto'
    # (appelé uniquement depuis le bouton "Rechercher sur OFF", pas à chaque frappe)
    if len(ciqual_results) >= CIQUAL_MIN_RESULTS:
        return ciqual_results

    return ciqual_results[:15]


@router.get("/ciqual-status")
def ciqual_status(db: Session = Depends(get_db)):
    try:
        count = db.query(CiqualFood).count()
        return {"available": count > 0, "count": count}
    except Exception:
        return {"available": False, "count": 0}

@router.get("/off-local-status")
def off_local_status(db: Session = Depends(get_db)):
    """Statut de la base OFF locale."""
    if not OFF_LOCAL_ENABLED:
        return {"enabled": False}
    try:
        count = db.query(OFFFood).count()
        from app.off_importer import _read_meta
        meta = _read_meta()
        return {
            "enabled": True,
            "count": count,
            "countries": meta.get("countries", []),
            "imported_at": meta.get("imported_at"),
            "update_interval": os.getenv("OFF_UPDATE_INTERVAL", "monthly"),
        }
    except Exception:
        return {"enabled": True, "count": 0, "countries": [], "imported_at": None}
