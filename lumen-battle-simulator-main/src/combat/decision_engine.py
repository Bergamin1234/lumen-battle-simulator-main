import logging
from dataclasses import dataclass, field
from typing import Optional, List, Set, Dict, Any, Tuple

from src.models.enums import Element, AgentState
from src.models.lumen import BattleTelemetry, MoveSlotInfo, TeamStatus, LumenMemberState, ActionPlan, AtomicAction
from src.models.combat_vision import CombatSnapshot, SkillSlot, EnemyTarget, CombatDecision, PositionInfo
from src.core.elements import get_elemental_multiplier
from src.core.codex import SPECIES_CATALOG
from src.combat.positioning import CombatPositioningController

logger = logging.getLogger("LumenaCombat")


@dataclass
class ActionDecision:
    """Decisão estruturada e explicável gerada pelo motor de combate legado."""
    action_type: str  # "MOVE", "SWITCH", "CONFIRM_VICTORY", "CLEAR_DEFEAT", "ADVANCE_DIALOG", "WAIT"
    target_slot: int  # Slot de golpe (0-3) ou slot de troca de criatura (0-5)
    target_name: str
    score: float
    reason: str
    confidence: float
    action_plan: ActionPlan = field(default_factory=ActionPlan)


class CombatDecisionEngine:
    """Motor de decisão e ranking determinístico para combate inteligente em malha fechada.

    Suporta N habilidades dinâmicas, controle tático de posicionamento e alcance, fraquezas elementais,
    e estados de combate completos (NO_TARGET, SEARCH_TARGET, APPROACH_TARGET, MAINTAIN_DISTANCE, USE_SKILL, HEAL, REASSESS, VICTORY, DEFEAT).
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("LumenaCombat")
        self.positioning_ctrl = CombatPositioningController()
        # Mapeamento de prioridades configuráveis de habilidades
        self.priority_weights: Dict[str, float] = {
            "ULTIMATE": 100.0,
            "HIGH_DAMAGE": 70.0,
            "CROWD_CONTROL": 60.0,
            "NORMAL_ATTACK": 40.0,
            "UTILITY": 30.0,
            "MOVEMENT": 20.0,
        }
        # Mapeamento rápido de espécies -> Elementos para inferência de fraqueza do inimigo
        self._species_element_cache: Dict[str, Tuple[Element, Optional[Element]]] = {}
        self._build_species_cache()

    def _build_species_cache(self) -> None:
        for entry in SPECIES_CATALOG:
            name = entry[1].lower()
            self._species_element_cache[name] = (entry[2], entry[3])

    def infer_enemy_elements(self, enemy_name: Optional[str]) -> Tuple[Element, Optional[Element]]:
        """Deduz o tipo elemental primário e secundário da espécie oponente pelo nome."""
        if enemy_name:
            clean = enemy_name.lower().strip()
            if clean in self._species_element_cache:
                return self._species_element_cache[clean]
        return Element.NORMAL, None

    def evaluate_combat_snapshot(
        self,
        snapshot: CombatSnapshot,
        recent_failed_skills: Optional[Set[str]] = None,
    ) -> CombatDecision:
        """Avalia um CombatSnapshot dinâmico e seleciona a melhor ação/habilidade considerando posicionamento e alcance."""
        failed_set = recent_failed_skills or set()

        # 1. Vitória
        if snapshot.victory_detected:
            return CombatDecision(
                action_type="CONFIRM_VICTORY",
                target_pos=(960, 540),
                reason="Inimigo derrotado. Confirmando vitória.",
                score=1000.0,
                confidence=1.0,
            )

        # 2. Derrota
        if snapshot.defeat_detected:
            return CombatDecision(
                action_type="CLEAR_DEFEAT",
                target_pos=(960, 540),
                reason="Lumen desmaiou ou combate perdido. Reconhecendo tela.",
                score=1000.0,
                confidence=1.0,
            )

        # 3. Diálogo Ativo
        if snapshot.dialog_active:
            return CombatDecision(
                action_type="ADVANCE_DIALOG",
                target_pos=(960, 540),
                reason="Caixa de diálogo ativa durante combate. Avançando texto.",
                score=100.0,
                confidence=0.9,
            )

        # 4. Validação de Percepção de Alvo e Jogador (Evita Ataques Cegos)
        if snapshot.in_battle:
            if not snapshot.target_enemy:
                self.logger.warning("⚠️ [PERCEPTION_FAILURE] Alvo inimigo não detectado na arena.")
                return CombatDecision(
                    action_type="WAIT",
                    reason="PERCEPTION_FAILURE: ENEMY_NOT_DETECTED (Ataque cego evitado)",
                    score=0.0,
                    confidence=0.0,
                )
            if not getattr(snapshot, "player_detected", True):
                self.logger.warning("⚠️ [PERCEPTION_FAILURE] Jogador não detectado na arena.")
                return CombatDecision(
                    action_type="WAIT",
                    reason="PERCEPTION_FAILURE: PLAYER_NOT_DETECTED (Ataque cego evitado)",
                    score=0.0,
                    confidence=0.0,
                )

        target = snapshot.target_enemy
        target_elem = (target.element if target else Element.NORMAL) or Element.NORMAL
        player_pos = snapshot.player_position or (960, 540)
        target_pos = target.center if target else None

        # 5. Avaliação de Habilidades Dinâmicas (Scoring Formula)
        candidates: List[Tuple[SkillSlot, float, str]] = []

        for skill in snapshot.available_skills:
            # Pula habilidades indisponíveis ou em cooldown ativo
            if not skill.available or skill.cooldown > 0 or skill.disabled:
                continue

            skill_id = skill.id or f"skill_slot_{skill.slot_index}"
            score = float(skill.power)
            reasons = [f"Poder Base: {skill.power}"]

            # Multiplicador Elemental
            elem = skill.element or Element.NORMAL
            mult = get_elemental_multiplier(elem, target_elem)
            score *= mult

            if mult >= 2.0:
                reasons.append(f"Super Efetivo ({mult:.1f}x) vs {target_elem.name}")
                score += 50.0
            elif mult <= 0.5:
                reasons.append(f"Pouco Efetivo ({mult:.1f}x) vs {target_elem.name}")
                score -= 30.0

            # Prioridade e Tipo
            if skill.range_type == "HEAL" and snapshot.player_hp <= 0.30:
                score += 100.0
                reasons.append("Cura Crítica Priorizada")
            elif skill.range_type == "RANGED":
                score += 15.0
                reasons.append("Ataque Ranged")

            # Finalização (Kill Shot)
            if target and target.hp_estimate <= 0.35 and mult >= 1.0:
                score += 30.0
                reasons.append("Oportunidade de Nocaute")

            # Penalidade por Falha Anterior na Mesma Ação
            if skill_id in failed_set or str(skill.slot_index) in failed_set or skill.skill_name in failed_set:
                score -= 60.0
                reasons.append("Penalidade: Ação anterior falhou ou não produziu efeito visual")

            candidates.append((skill, score, " | ".join(reasons)))

        if candidates:
            # Ordena e seleciona a melhor habilidade
            candidates.sort(key=lambda c: c[1], reverse=True)
            best_skill, best_score, best_reason = candidates[0]

            # 5. Avaliação Tática de Posicionamento e Alcance (quando snapshot possui medição de posicionamento)
            if target_pos and snapshot.position_info is not None:
                pos_state, move_key, dist = self.positioning_ctrl.evaluate_positioning(
                    player_pos, target_pos, best_skill
                )

                if pos_state == "APPROACH_TARGET":
                    return CombatDecision(
                        action_type="APPROACH_TARGET",
                        selected_skill=best_skill,
                        target_pos=target_pos,
                        move_direction=move_key,
                        reason=f"Alvo fora de alcance ({dist:.1f}px). Aproximando via '{move_key}'.",
                        score=best_score + 10.0,
                        confidence=0.90,
                    )
                elif pos_state == "MAINTAIN_DISTANCE":
                    return CombatDecision(
                        action_type="MAINTAIN_DISTANCE",
                        selected_skill=best_skill,
                        target_pos=target_pos,
                        move_direction=move_key,
                        reason=f"Muito próximo para ataque à distância ({dist:.1f}px). Recuando via '{move_key}'.",
                        score=best_score + 5.0,
                        confidence=0.85,
                    )

            # Posição pronta -> Usa a habilidade
            return CombatDecision(
                action_type="USE_SKILL",
                selected_skill=best_skill,
                target_pos=(best_skill.center_x, best_skill.center_y),
                hotkey=best_skill.hotkey,
                reason=best_reason,
                score=best_score,
                confidence=best_skill.confidence,
            )

        # Se não há habilidades prontas mas há botão FIGHT
        if snapshot.fight_button_pos:
            return CombatDecision(
                action_type="OPEN_FIGHT_MENU",
                target_pos=snapshot.fight_button_pos,
                reason="Menu de habilidades fechado. Clicando em FIGHT para abrir opções.",
                score=10.0,
                confidence=0.8,
            )

        # Se nenhum alvo na cena
        if not target and snapshot.in_battle:
            return CombatDecision(
                action_type="SEARCH_TARGET",
                target_pos=(960, 540),
                reason="Nenhum alvo focado na arena. Buscando oponente.",
                score=5.0,
                confidence=0.7,
            )

        return CombatDecision(
            action_type="WAIT",
            target_pos=(960, 540),
            reason="NO_SKILL_AVAILABLE: Aguardando animação ou recarga de habilidades.",
            score=0.0,
            confidence=0.5,
        )

    def evaluate_turn(
        self,
        telemetry: BattleTelemetry,
        team: Optional[TeamStatus] = None,
        recent_failed_targets: Optional[Set[str]] = None,
    ) -> ActionDecision:
        """Avalia o estado de combate legado e seleciona a ação de maior pontuação/sobrevivência."""
        failed_set = recent_failed_targets or set()

        if telemetry.victory_detected:
            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_CENTER", target="center", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=0.3),
                    AtomicAction(action_type="CLICK_CENTER", target="center", duration=0.2),
                ],
                description="Avançar diálogo de vitória e recolher recompensas",
            )
            return ActionDecision(
                action_type="CONFIRM_VICTORY",
                target_slot=-1,
                target_name="VictoryScreen",
                score=1000.0,
                reason="Inimigo derrotado. Confirmando vitória e fechando tela.",
                confidence=1.0,
                action_plan=plan,
            )

        if telemetry.defeat_detected:
            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_CENTER", target="center", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=0.5),
                ],
                description="Reconhecer tela de derrota e fechar modal",
            )
            return ActionDecision(
                action_type="CLEAR_DEFEAT",
                target_slot=-1,
                target_name="DefeatScreen",
                score=1000.0,
                reason="Lumen desmaiou ou combate perdido. Reconhecendo tela.",
                confidence=1.0,
                action_plan=plan,
            )

        if telemetry.dialog_active:
            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_CENTER", target="center", duration=0.15),
                ],
                description="Avançar diálogo durante batalha",
            )
            return ActionDecision(
                action_type="ADVANCE_DIALOG",
                target_slot=-1,
                target_name="DialogBox",
                score=500.0,
                reason="Diálogo de combate ativo. Clicando no centro para avançar.",
                confidence=1.0,
                action_plan=plan,
            )

        # Troca de Lumen se HP crítico
        if team and (telemetry.player_hp_pct <= 0.25):
            for member in team.members:
                if member.slot != team.active_slot and member.hp_percentage > 0.40 and not member.is_fainted:
                    plan = ActionPlan(
                        actions=[
                            AtomicAction(action_type="CLICK_SWITCH", target="switch_button", duration=0.2),
                            AtomicAction(action_type="WAIT", target="wait", duration=0.3),
                            AtomicAction(action_type="CLICK_LUMEN", target=f"slot_{member.slot}", duration=0.2),
                        ],
                        description=f"Trocar para {member.nickname} (HP {member.hp_percentage*100:.0f}%)",
                    )
                    return ActionDecision(
                        action_type="SWITCH",
                        target_slot=member.slot,
                        target_name=member.nickname,
                        score=200.0,
                        reason=f"HP crítico do Lumen ativo ({telemetry.player_hp_pct*100:.0f}%). Troca de preservação para {member.nickname}.",
                        confidence=0.95,
                        action_plan=plan,
                    )

        # Seleção de Golpes
        best_move = self._rank_available_moves(telemetry, failed_set)
        if best_move:
            return best_move

        return self._generate_fallback_decision(telemetry)

    def _rank_available_moves(
        self,
        telemetry: BattleTelemetry,
        failed_set: Set[str],
    ) -> Optional[ActionDecision]:
        if not telemetry.available_moves:
            return None

        enemy_elem_1, enemy_elem_2 = self.infer_enemy_elements(telemetry.enemy_lumen_name)
        candidates: List[ActionDecision] = []

        for move in telemetry.available_moves:
            if not move.is_available or move.current_pp <= 0:
                continue

            move_id = f"move_{move.slot_index}_{move.name}"
            slot_id = f"move_slot_{move.slot_index}"
            score = float(move.power)
            reason_parts = [f"Poder: {move.power}"]

            mult_1 = get_elemental_multiplier(move.element, enemy_elem_1)
            mult_2 = get_elemental_multiplier(move.element, enemy_elem_2) if enemy_elem_2 else 1.0
            mult = mult_1 * mult_2
            score *= mult

            if mult >= 2.0:
                score += 50.0
                reason_parts.append(f"Super Efetivo ({mult:.1f}x) vs {enemy_elem_1.name}")
            elif mult <= 0.5:
                score -= 30.0
                reason_parts.append(f"Pouco Efetivo ({mult:.1f}x)")
            else:
                reason_parts.append("Dano Neutro (1.0x)")

            if telemetry.enemy_hp_pct <= 0.35 and mult >= 1.0:
                score += 30.0
                reason_parts.append(f"Oportunidade de nocaute (HP Oponente {telemetry.enemy_hp_pct*100:.0f}%)")

            if move_id in failed_set or slot_id in failed_set or f"slot_{move.slot_index}" in failed_set:
                score -= 50.0
                reason_parts.append("Penalidade por falha anterior na mesma ação")

            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_FIGHT", target="fight_button", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=0.3),
                    AtomicAction(action_type="CLICK_MOVE", target=f"slot_{move.slot_index}", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=1.0),
                ],
                description=f"Executar golpe {move.name} no Slot {move.slot_index}",
            )

            candidates.append(
                ActionDecision(
                    action_type="MOVE",
                    target_slot=move.slot_index,
                    target_name=move.name,
                    score=score,
                    reason=" | ".join(reason_parts),
                    confidence=0.90,
                    action_plan=plan,
                )
            )

        if not candidates:
            return None

        return max(candidates, key=lambda c: c.score)

    def _generate_fallback_decision(self, telemetry: BattleTelemetry) -> ActionDecision:
        if telemetry.fight_button_pos is not None:
            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_FIGHT", target="fight_button", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=0.4),
                ],
                description="Abrir menu de golpes via botão FIGHT",
            )
            return ActionDecision(
                action_type="MOVE",
                target_slot=0,
                target_name="OpenFightMenu",
                score=10.0,
                reason="Percepção de slots incompleta. Clicando no botão FIGHT para abrir menu.",
                confidence=0.75,
                action_plan=plan,
            )

        plan = ActionPlan(
            actions=[
                AtomicAction(action_type="CLICK_CENTER", target="center", duration=0.2),
                AtomicAction(action_type="WAIT", target="wait", duration=0.5),
            ],
            description="Avançar interface de combate pelo centro",
        )
        return ActionDecision(
            action_type="ADVANCE_DIALOG",
            target_slot=-1,
            target_name="ScreenCenter",
            score=5.0,
            reason="Nenhum botão de combate detectado. Clicando no centro para avançar animação.",
            confidence=0.50,
            action_plan=plan,
        )
