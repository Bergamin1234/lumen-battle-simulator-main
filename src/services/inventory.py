from dataclasses import dataclass
from src.models.lumen import Lumen


@dataclass
class Equipment:
    name: str
    stat_bonus: str = "hp"
    bonus_value: int = 10


class InventoryService:
    @staticmethod
    def equip_item(lumen: Lumen, item: Equipment) -> bool:
        """Equipa um item no Lumen se ele ainda não estiver equipado."""
        if not hasattr(lumen, "equipped_items"):
            lumen.equipped_items = []

        if item not in lumen.equipped_items:
            lumen.equipped_items.append(item)
            lumen.current_hp = min(lumen.current_hp, lumen.total_hp)
            return True
        return False

    @staticmethod
    def unequip_item(lumen: Lumen, item_name: str) -> bool:
        """Desequipa um item pelo nome."""
        if not hasattr(lumen, "equipped_items"):
            return False

        for item in lumen.equipped_items:
            if item.name.lower() == item_name.lower():
                lumen.equipped_items.remove(item)
                return True
        return False