from src.models.lumen import Lumen, Equipment

class InventoryService:
    @staticmethod
    def equip_item(lumen: Lumen, item: Equipment) -> bool:
        """Equipa um item no Lumen se ele ainda não estiver equipado."""
        if item not in lumen.equipped_items:
            lumen.equipped_items.append(item)
            lumen.current_hp = min(lumen.current_hp, lumen.total_hp)
            return True
        return False

    @staticmethod
    def unequip_item(lumen: Lumen, item_name: str) -> bool:
        """Desequipa um item pelo nome."""
        for item in lumen.equipped_items:
            if item.name.lower() == item_name.lower():
                lumen.equipped_items.remove(item)
                return True
        return False