# src/database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base

ENGINE = create_engine("sqlite:///lumen_simulator.db", echo=False)
SessionLocal = sessionmaker(bind=ENGINE)

def init_db():
    Base.metadata.create_all(ENGINE)