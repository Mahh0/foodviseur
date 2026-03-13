from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("/", response_model=schemas.GoalOut)
def get_goals(db: Session = Depends(get_db)):
    goal = crud.get_goal(db)
    if not goal:
        # Return defaults
        return schemas.GoalOut(id=0, calories=2000, proteins=150, carbs=250, fats=70)
    return goal


@router.put("/", response_model=schemas.GoalOut)
def set_goals(goal: schemas.GoalCreate, db: Session = Depends(get_db)):
    return crud.upsert_goal(db, goal)
