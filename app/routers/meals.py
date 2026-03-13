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
