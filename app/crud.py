import os
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app import models, schemas
from app.schemas import MEAL_LABELS

MEAL_ORDER = ["petit_dej", "dejeuner", "diner", "encas"]
RECENT_FOODS_LIMIT = int(os.getenv("RECENT_FOODS_LIMIT", "8"))


# ─── Goals ─────────────────────────────────────────────────────────────────

def get_goal(db: Session) -> Optional[models.Goal]:
    return db.query(models.Goal).first()


def upsert_goal(db: Session, goal: schemas.GoalCreate) -> models.Goal:
    db_goal = db.query(models.Goal).first()
    if db_goal:
        for field, value in goal.model_dump().items():
            setattr(db_goal, field, value)
    else:
        db_goal = models.Goal(**goal.model_dump())
        db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal


# ─── Food cache ─────────────────────────────────────────────────────────────

def get_food_by_barcode(db: Session, barcode: str) -> Optional[models.FoodCache]:
    return db.query(models.FoodCache).filter(models.FoodCache.barcode == barcode).first()


def get_food_by_off_id(db: Session, off_id: str) -> Optional[models.FoodCache]:
    return db.query(models.FoodCache).filter(models.FoodCache.off_id == off_id).first()


def get_food_by_id(db: Session, food_id: int) -> Optional[models.FoodCache]:
    return db.query(models.FoodCache).filter(models.FoodCache.id == food_id).first()


def cache_food(db: Session, food: schemas.FoodItem) -> models.FoodCache:
    existing = None
    if food.barcode:
        existing = get_food_by_barcode(db, food.barcode)
    if not existing and food.off_id:
        existing = get_food_by_off_id(db, food.off_id)

    if existing:
        for field, value in food.model_dump(exclude={"id"}).items():
            if value is not None:
                setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing

    db_food = models.FoodCache(**food.model_dump(exclude={"id"}))
    db.add(db_food)
    db.commit()
    db.refresh(db_food)
    return db_food


def save_custom_food(db: Session, food: schemas.FoodItem) -> models.FoodCache:
    """Persiste un aliment saisi manuellement dans food_cache."""
    db_food = models.FoodCache(
        name=food.name,
        brand=food.brand,
        calories_100g=food.calories_100g,
        proteins_100g=food.proteins_100g,
        carbs_100g=food.carbs_100g,
        fats_100g=food.fats_100g,
        is_custom=True,
    )
    db.add(db_food)
    db.commit()
    db.refresh(db_food)
    return db_food


def delete_custom_food(db: Session, food_id: int) -> bool:
    """Supprime un aliment custom de food_cache (uniquement si is_custom=True)."""
    db_food = db.query(models.FoodCache).filter(
        models.FoodCache.id == food_id,
        models.FoodCache.is_custom == True,
    ).first()
    if not db_food:
        return False
    db.delete(db_food)
    db.commit()
    return True


def get_recent_foods(db: Session, limit: int = RECENT_FOODS_LIMIT) -> list[dict]:
    """
    Retourne les aliments récemment ajoutés au journal,
    triés du plus récent au plus ancien, avec la dernière quantité utilisée.
    Dédupliqués par food_cache_id (ou food_name si pas de cache_id).
    """
    # Sous-requête : dernière entrée par aliment
    subq = (
        db.query(
            models.MealEntry.food_cache_id,
            models.MealEntry.food_name,
            models.MealEntry.brand,
            models.MealEntry.calories_100g,
            models.MealEntry.proteins_100g,
            models.MealEntry.carbs_100g,
            models.MealEntry.fats_100g,
            models.MealEntry.quantity_g,
            func.max(models.MealEntry.logged_at).label("last_used"),
        )
        .group_by(
            func.coalesce(
                func.cast(models.MealEntry.food_cache_id, models.String),
                models.MealEntry.food_name
            )
        )
        .order_by(desc("last_used"))
        .limit(limit)
        .all()
    )

    results = []
    for row in subq:
        # Récupérer is_custom depuis food_cache si possible
        is_custom = False
        fc_id = row.food_cache_id
        if fc_id:
            fc = db.query(models.FoodCache).filter(models.FoodCache.id == fc_id).first()
            if fc:
                is_custom = fc.is_custom

        results.append({
            "id": fc_id,
            "name": row.food_name,
            "brand": row.brand,
            "calories_100g": row.calories_100g,
            "proteins_100g": row.proteins_100g,
            "carbs_100g": row.carbs_100g,
            "fats_100g": row.fats_100g,
            "last_quantity_g": row.quantity_g,
            "last_used": row.last_used.isoformat() if row.last_used else None,
            "is_custom": is_custom,
        })
    return results


# ─── Meal entries ────────────────────────────────────────────────────────────

def create_meal_entry(db: Session, entry: schemas.MealEntryCreate) -> models.MealEntry:
    entry_date = entry.date or date.today()
    ratio = entry.quantity_g / 100.0
    db_entry = models.MealEntry(
        date=entry_date,
        meal_type=entry.meal_type,
        food_name=entry.food_name,
        brand=entry.brand,
        quantity_g=entry.quantity_g,
        calories=round(entry.calories_100g * ratio, 1),
        proteins=round(entry.proteins_100g * ratio, 1),
        carbs=round(entry.carbs_100g * ratio, 1),
        fats=round(entry.fats_100g * ratio, 1),
        calories_100g=entry.calories_100g,
        proteins_100g=entry.proteins_100g,
        carbs_100g=entry.carbs_100g,
        fats_100g=entry.fats_100g,
        notes=entry.notes,
        food_cache_id=entry.food_cache_id,
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


def get_entries_for_date(db: Session, target_date: date) -> list[models.MealEntry]:
    return (
        db.query(models.MealEntry)
        .filter(models.MealEntry.date == target_date)
        .order_by(models.MealEntry.logged_at)
        .all()
    )


def update_meal_entry(db: Session, entry_id: int, update: schemas.MealEntryUpdate) -> Optional[models.MealEntry]:
    db_entry = db.query(models.MealEntry).filter(models.MealEntry.id == entry_id).first()
    if not db_entry:
        return None

    if update.quantity_g is not None and update.quantity_g > 0:
        db_entry.quantity_g = update.quantity_g
        ratio = update.quantity_g / 100.0
        db_entry.calories = round(db_entry.calories_100g * ratio, 1)
        db_entry.proteins = round(db_entry.proteins_100g * ratio, 1)
        db_entry.carbs = round(db_entry.carbs_100g * ratio, 1)
        db_entry.fats = round(db_entry.fats_100g * ratio, 1)

    if update.meal_type is not None:
        db_entry.meal_type = update.meal_type

    if update.notes is not None:
        db_entry.notes = update.notes

    db.commit()
    db.refresh(db_entry)
    return db_entry


def delete_meal_entry(db: Session, entry_id: int) -> bool:
    db_entry = db.query(models.MealEntry).filter(models.MealEntry.id == entry_id).first()
    if not db_entry:
        return False
    db.delete(db_entry)
    db.commit()
    return True


def get_daily_summary(db: Session, target_date: date) -> schemas.DailySummary:
    entries = get_entries_for_date(db, target_date)
    entry_outs = [schemas.MealEntryOut.model_validate(e) for e in entries]

    groups = []
    for mt in MEAL_ORDER:
        group_entries = [e for e in entry_outs if e.meal_type == mt]
        groups.append(schemas.MealGroup(
            meal_type=mt,
            label=MEAL_LABELS[mt],
            total_calories=round(sum(e.calories for e in group_entries), 1),
            total_proteins=round(sum(e.proteins for e in group_entries), 1),
            total_carbs=round(sum(e.carbs for e in group_entries), 1),
            total_fats=round(sum(e.fats for e in group_entries), 1),
            entries=group_entries,
        ))

    return schemas.DailySummary(
        date=target_date,
        total_calories=round(sum(e.calories for e in entry_outs), 1),
        total_proteins=round(sum(e.proteins for e in entry_outs), 1),
        total_carbs=round(sum(e.carbs for e in entry_outs), 1),
        total_fats=round(sum(e.fats for e in entry_outs), 1),
        meals=groups,
    )
