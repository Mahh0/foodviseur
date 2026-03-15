from datetime import datetime, date
from typing import Optional, Literal
from pydantic import BaseModel

MealType = Literal["petit_dej", "dejeuner", "diner", "encas"]

MEAL_LABELS = {
    "petit_dej": "Petit-déjeuner",
    "dejeuner": "Déjeuner",
    "diner": "Dîner",
    "encas": "En-cas",
}

class GoalBase(BaseModel):
    calories: float = 2000.0
    proteins: float = 150.0
    carbs: float = 250.0
    fats: float = 70.0
    fibers: float = 25.0

class GoalCreate(GoalBase):
    pass

class GoalOut(GoalBase):
    id: int
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class FoodItem(BaseModel):
    id: Optional[int] = None
    barcode: Optional[str] = None
    off_id: Optional[str] = None
    name: str
    brand: Optional[str] = None
    calories_100g: float = 0.0
    proteins_100g: float = 0.0
    carbs_100g: float = 0.0
    fats_100g: float = 0.0
    fibers_100g: float = 0.0
    image_url: Optional[str] = None
    is_custom: bool = False
    class Config:
        from_attributes = True

class RecentFoodItem(BaseModel):
    id: Optional[int] = None
    name: str
    brand: Optional[str] = None
    calories_100g: float = 0.0
    proteins_100g: float = 0.0
    carbs_100g: float = 0.0
    fats_100g: float = 0.0
    fibers_100g: float = 0.0
    last_quantity_g: float = 100.0
    last_used: Optional[str] = None
    is_custom: bool = False

class MealEntryCreate(BaseModel):
    food_name: str
    brand: Optional[str] = None
    quantity_g: float
    meal_type: MealType = "dejeuner"
    calories_100g: float = 0.0
    proteins_100g: float = 0.0
    carbs_100g: float = 0.0
    fats_100g: float = 0.0
    fibers_100g: float = 0.0
    notes: Optional[str] = None
    food_cache_id: Optional[int] = None
    date: Optional[date] = None

class MealEntryUpdate(BaseModel):
    quantity_g: Optional[float] = None
    meal_type: Optional[MealType] = None
    notes: Optional[str] = None

class MealEntryOut(BaseModel):
    id: int
    date: date
    logged_at: datetime
    meal_type: str
    food_name: str
    brand: Optional[str] = None
    quantity_g: float
    calories: float
    proteins: float
    carbs: float
    fats: float
    fibers: float = 0.0
    calories_100g: float
    proteins_100g: float
    carbs_100g: float
    fats_100g: float
    fibers_100g: float = 0.0
    notes: Optional[str] = None
    class Config:
        from_attributes = True

class MealGroup(BaseModel):
    meal_type: str
    label: str
    total_calories: float
    total_proteins: float
    total_carbs: float
    total_fats: float
    total_fibers: float
    entries: list[MealEntryOut]

class DailySummary(BaseModel):
    date: date
    total_calories: float
    total_proteins: float
    total_carbs: float
    total_fats: float
    total_fibers: float
    meals: list[MealGroup]
