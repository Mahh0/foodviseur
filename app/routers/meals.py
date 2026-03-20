from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api/meals", tags=["meals"])


@router.get("/summary/{target_date}", response_model=schemas.DailySummary)
def get_summary(target_date: date, db: Session = Depends(get_db)):
    return crud.get_daily_summary(db, target_date)


@router.get("/today", response_model=schemas.DailySummary)
def get_today(db: Session = Depends(get_db)):
    return crud.get_daily_summary(db, date.today())


@router.post("/", response_model=schemas.MealEntryOut)
def add_meal(entry: schemas.MealEntryCreate, db: Session = Depends(get_db)):
    return crud.create_meal_entry(db, entry)


@router.patch("/{entry_id}", response_model=schemas.MealEntryOut)
def update_meal(entry_id: int, update: schemas.MealEntryUpdate, db: Session = Depends(get_db)):
    result = crud.update_meal_entry(db, entry_id, update)
    if not result:
        raise HTTPException(status_code=404, detail="Entry not found")
    return result


@router.delete("/{entry_id}")
def delete_meal(entry_id: int, db: Session = Depends(get_db)):
    if not crud.delete_meal_entry(db, entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}


from pydantic import BaseModel as PydanticBase

class CopyMealRequest(PydanticBase):
    from_date: date
    from_meal_type: str
    to_date: date
    to_meal_type: str


@router.post("/copy")
def copy_meal(req: CopyMealRequest, db: Session = Depends(get_db)):
    """Copie tous les aliments d'un repas source vers un repas cible."""
    from app.models import MealEntry
    from datetime import datetime
    entries = (
        db.query(MealEntry)
        .filter(MealEntry.date == req.from_date, MealEntry.meal_type == req.from_meal_type)
        .all()
    )
    if not entries:
        raise HTTPException(status_code=404, detail="Aucun aliment dans ce repas")
    copied = 0
    for e in entries:
        new_entry = MealEntry(
            date=req.to_date,
            meal_type=req.to_meal_type,
            food_name=e.food_name,
            brand=e.brand,
            quantity_g=e.quantity_g,
            calories=e.calories,
            proteins=e.proteins,
            carbs=e.carbs,
            fats=e.fats,
            fibers=e.fibers,
            calories_100g=e.calories_100g,
            proteins_100g=e.proteins_100g,
            carbs_100g=e.carbs_100g,
            fats_100g=e.fats_100g,
            fibers_100g=e.fibers_100g,
            notes=e.notes,
            food_cache_id=e.food_cache_id,
        )
        db.add(new_entry)
        copied += 1
    db.commit()
    return {"copied": copied}
