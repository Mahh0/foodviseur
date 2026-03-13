from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, Boolean
from app.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    calories = Column(Float, default=2000.0)
    proteins = Column(Float, default=150.0)
    carbs = Column(Float, default=250.0)
    fats = Column(Float, default=70.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FoodCache(Base):
    __tablename__ = "food_cache"

    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String, unique=True, index=True, nullable=True)
    off_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    calories_100g = Column(Float, default=0.0)
    proteins_100g = Column(Float, default=0.0)
    carbs_100g = Column(Float, default=0.0)
    fats_100g = Column(Float, default=0.0)
    image_url = Column(String, nullable=True)
    cached_at = Column(DateTime, default=datetime.utcnow)
    is_custom = Column(Boolean, default=False, nullable=False)


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=date.today, index=True)
    logged_at = Column(DateTime, default=datetime.utcnow)
    meal_type = Column(String, default="dejeuner", nullable=False)
    food_name = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    quantity_g = Column(Float, nullable=False)
    calories = Column(Float, default=0.0)
    proteins = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    fats = Column(Float, default=0.0)
    calories_100g = Column(Float, default=0.0)
    proteins_100g = Column(Float, default=0.0)
    carbs_100g = Column(Float, default=0.0)
    fats_100g = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    food_cache_id = Column(Integer, nullable=True)


class CiqualFood(Base):
    __tablename__ = "ciqual_foods"

    id = Column(Integer, primary_key=True, index=True)
    ciqual_code = Column(Integer, unique=True, index=True, nullable=False)
    name_fr = Column(String, nullable=False, index=True)
    calories_100g = Column(Float, default=0.0)
    proteins_100g = Column(Float, default=0.0)
    carbs_100g = Column(Float, default=0.0)
    fats_100g = Column(Float, default=0.0)
