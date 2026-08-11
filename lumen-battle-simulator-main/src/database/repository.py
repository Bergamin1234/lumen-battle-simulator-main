from sqlalchemy.orm import Session
from src.database.models import DBClassLumen, DBBattleLog
from src.models.lumen import Lumen
from src.models.enums import Element, Rarity

class LumenRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_lumen(self, lumen: Lumen) -> DBClassLumen:
        """Persiste um Lumen no banco SQLite."""
        db_lumen = DBClassLumen(
            name=lumen.name,
            element=lumen.element,
            rarity=lumen.rarity,
            level=lumen.level,
            experience=lumen.experience,
            base_hp=lumen.base_hp,
            base_attack=lumen.base_attack,
            base_defense=lumen.base_defense,
            base_speed=lumen.base_speed
        )
        self.session.add(db_lumen)
        self.session.commit()
        self.session.refresh(db_lumen)
        return db_lumen

    def get_all(self) -> list[DBClassLumen]:
        """Retorna todos os Lumens salvos."""
        return self.session.query(DBClassLumen).all()

    def log_battle(self, winner_name: str, loser_name: str, turns: int):
        """Registra o histórico de batalhas."""
        log = DBBattleLog(winner_name=winner_name, loser_name=loser_name, turns=turns)
        self.session.add(log)
        self.session.commit()