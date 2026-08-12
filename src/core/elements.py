from src.models.enums import Element

# Tabela de Eficiência: 2.0 (Super Efetivo), 0.5 (Pouco Efetivo), 0.0 (Imunidade)
ELEMENTAL_CHART: dict[Element, dict[Element, float]] = {
    Element.NORMAL: {Element.ROCK: 0.5, Element.STEEL: 0.5, Element.GHOST: 0.0},
    Element.FIRE: {Element.GRASS: 2.0, Element.ICE: 2.0, Element.BUG: 2.0, Element.STEEL: 2.0, Element.FIRE: 0.5, Element.WATER: 0.5, Element.ROCK: 0.5, Element.DRAGON: 0.5},
    Element.WATER: {Element.FIRE: 2.0, Element.GROUND: 2.0, Element.ROCK: 2.0, Element.WATER: 0.5, Element.GRASS: 0.5, Element.DRAGON: 0.5},
    Element.GRASS: {Element.WATER: 2.0, Element.GROUND: 2.0, Element.ROCK: 2.0, Element.FIRE: 0.5, Element.GRASS: 0.5, Element.POISON: 0.5, Element.FLYING: 0.5, Element.BUG: 0.5, Element.DRAGON: 0.5, Element.STEEL: 0.5},
    Element.ELECTRIC: {Element.WATER: 2.0, Element.FLYING: 2.0, Element.ELECTRIC: 0.5, Element.GRASS: 0.5, Element.DRAGON: 0.5, Element.GROUND: 0.0},
    Element.ICE: {Element.GRASS: 2.0, Element.GROUND: 2.0, Element.FLYING: 2.0, Element.DRAGON: 2.0, Element.FIRE: 0.5, Element.WATER: 0.5, Element.ICE: 0.5, Element.STEEL: 0.5},
    Element.FIGHTING: {Element.NORMAL: 2.0, Element.ICE: 2.0, Element.ROCK: 2.0, Element.DARK: 2.0, Element.STEEL: 2.0, Element.POISON: 0.5, Element.FLYING: 0.5, Element.PSYCHIC: 0.5, Element.BUG: 0.5, Element.FAIRY: 0.5, Element.GHOST: 0.0},
    Element.POISON: {Element.GRASS: 2.0, Element.FAIRY: 2.0, Element.POISON: 0.5, Element.GROUND: 0.5, Element.ROCK: 0.5, Element.GHOST: 0.5, Element.STEEL: 0.0},
    Element.GROUND: {Element.FIRE: 2.0, Element.ELECTRIC: 2.0, Element.POISON: 2.0, Element.ROCK: 2.0, Element.STEEL: 2.0, Element.GRASS: 0.5, Element.BUG: 0.5, Element.FLYING: 0.0},
    Element.FLYING: {Element.GRASS: 2.0, Element.FIGHTING: 2.0, Element.BUG: 2.0, Element.ELECTRIC: 0.5, Element.ROCK: 0.5, Element.STEEL: 0.5},
    Element.PSYCHIC: {Element.FIGHTING: 2.0, Element.POISON: 2.0, Element.PSYCHIC: 0.5, Element.STEEL: 0.5, Element.DARK: 0.0},
    Element.BUG: {Element.GRASS: 2.0, Element.PSYCHIC: 2.0, Element.DARK: 2.0, Element.FIRE: 0.5, Element.FIGHTING: 0.5, Element.POISON: 0.5, Element.FLYING: 0.5, Element.GHOST: 0.5, Element.STEEL: 0.5, Element.FAIRY: 0.5},
    Element.ROCK: {Element.FIRE: 2.0, Element.ICE: 2.0, Element.FLYING: 2.0, Element.BUG: 2.0, Element.FIGHTING: 0.5, Element.GROUND: 0.5, Element.STEEL: 0.5},
    Element.GHOST: {Element.PSYCHIC: 2.0, Element.GHOST: 2.0, Element.DARK: 0.5, Element.NORMAL: 0.0},
    Element.DRAGON: {Element.DRAGON: 2.0, Element.STEEL: 0.5, Element.FAIRY: 0.0},
    Element.DARK: {Element.PSYCHIC: 2.0, Element.GHOST: 2.0, Element.FIGHTING: 0.5, Element.DARK: 0.5, Element.FAIRY: 0.5},
    Element.STEEL: {Element.ICE: 2.0, Element.ROCK: 2.0, Element.FAIRY: 2.0, Element.FIRE: 0.5, Element.WATER: 0.5, Element.ELECTRIC: 0.5, Element.STEEL: 0.5},
    Element.FAIRY: {Element.FIGHTING: 2.0, Element.DRAGON: 2.0, Element.DARK: 2.0, Element.FIRE: 0.5, Element.POISON: 0.5, Element.STEEL: 0.5}
}

def get_elemental_multiplier(attacker_type: Element, defender_primary: Element, defender_secondary: Element = None) -> float:
    mult = ELEMENTAL_CHART.get(attacker_type, {}).get(defender_primary, 1.0)
    if defender_secondary:
        mult *= ELEMENTAL_CHART.get(attacker_type, {}).get(defender_secondary, 1.0)
    return mult