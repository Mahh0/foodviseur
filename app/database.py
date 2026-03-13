import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/foodviseur.db")

# For local dev, use a local path
if DATABASE_URL == "sqlite:////data/foodviseur.db" and not os.path.exists("/data"):
    os.makedirs("/tmp/foodviseur", exist_ok=True)
    DATABASE_URL = "sqlite:////tmp/foodviseur/foodviseur.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)
