# src/database/models.py
from sqlalchemy import Column, Integer, String, Float, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from src.models.enums import Element, Rarity

Base = declarative_base()

class DBClassLumen(Base):
    __tablename__ = "lumens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    element = Column(SQLEnum(Element), nullable=False)
    rarity = Column(SQLEnum(Rarity), nullable=False)
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    base_hp = Column(Integer, default=100)
    base_attack = Column(Integer, default=20)
    base_defense = Column(Integer, default=15)
    base_speed = Column(Integer, default=10)

class DBBattleLog(Base):
    __tablename__ = "battle_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    winner_name = Column(String, nullable=False)
    loser_name = Column(String, nullable=False)
    turns = Column(Integer, nullable=False)