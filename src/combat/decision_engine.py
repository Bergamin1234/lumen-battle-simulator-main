import logging
from dataclasses import dataclass, field
from typing import Optional, List, Set, Dict, Any, Tuple

from src.models.enums import Element, AgentState
from src.models.lumen import BattleTelemetry, MoveSlotInfo, TeamStatus, LumenMemberState, ActionPlan, AtomicAction
from src.core.elements import get_elemental_multiplier
from src.core.codex import SPECIES_CATALOG


@dataclass
class ActionDecision:
    """Decisão estruturada e explicável gerada pelo motor de combate."""
    action_type: str  # "MOVE", "SWITCH", "CONFIRM_VICTORY", "CLEAR_DEFEAT", "ADVANCE_DIALOG", "WAIT"
    target_slot: int  # Slot de golpe (0-3) ou slot de troca de criatura (0-5)
    target_name: str
    score: float
    reason: str
    confidence: float
    action_plan: ActionPlan = field(default_factory=ActionPlan)


class CombatDecisionEngine:
    """Motor de decisão e ranking determinístico para combate inteligente em malha fechada."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("LumenaCombat")
        # Mapeamento rápido de espécies -> Elementos para inferência de fraqueza do inimigo
        self._species_element_cache: Dict[str, Tuple[Element, Optional[Element]]] = {}
        self._build_species_cache()

    def _build_species_cache(self) -> None:
        for entry in SPECIES_CATALOG:
            # entry: (id, nome, tipo_1, tipo_2, ...)
            name = entry[1].lower()
            self._species_element_cache[name] = (entry[2], entry[3])

    def infer_enemy_elements(self, enemy_name: Optional[str]) -> Tuple[Element, Optional[Element]]:
        """Deduz o tipo elemental primário e secundário da espécie oponente pelo nome."""
        if enemy_name:
            clean = enemy_name.lower().strip()
            if clean in self._species_element_cache:
                return self._species_element_cache[clean]
        # Padrão desconhecido: NORMAL
        return Element.NORMAL, None

    def evaluate_turn(
        self,
        telemetry: BattleTelemetry,
        team: Optional[TeamStatus] = None,
        recent_failed_targets: Optional[Set[str]] = None,
    ) -> ActionDecision:
        """Avalia o estado de combate atual e seleciona a ação de maior pontuação/sobrevivência."""
        failed_set = recent_failed_targets or set()

        # 1. Tratamento de Vitória Concluída
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

        # 2. Tratamento de Derrota
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

        # 3. Tratamento de Diálogo de Texto Ativo durante a Batalha
        if telemetry.dialog_active:
            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_CENTER", target="center", duration=0.15),
                ],
                description="Avançar diálogo de combate",
            )
            return ActionDecision(
                action_type="ADVANCE_DIALOG",
                target_slot=-1,
                target_name="CombatDialog",
                score=500.0,
                reason="Diálogo ativo na tela de batalha. Avançando texto.",
                confidence=0.9,
                action_plan=plan,
            )

        # 4. Avaliação de Sobrevivência e Troca de Criatura (SWITCH)
        switch_decision = self._evaluate_team_switch(telemetry, team, failed_set)
        if switch_decision is not None and switch_decision.score > 85.0:
            return switch_decision

        # 5. Avaliação e Ranking dos 4 Slots de Ataque
        move_decision = self._evaluate_moves(telemetry, team, failed_set)
        if move_decision is not None:
            # Se a melhor jogada for viável, retorna
            if move_decision.score > 0:
                return move_decision
            # Se a melhor jogada for inviável (ex: sem PP) e houver opção de troca, prefere troca
            if switch_decision is not None and switch_decision.score > 0:
                return switch_decision

        # 6. Fallback de Segurança caso percepção esteja incompleta
        return self._generate_fallback_decision(telemetry)

    def _evaluate_team_switch(
        self,
        telemetry: BattleTelemetry,
        team: Optional[TeamStatus],
        failed_set: Set[str],
    ) -> Optional[ActionDecision]:
        """Avalia se a criatura ativa corre risco iminente de desmaio ou está sem PP para trocar de Lumen."""
        if team is None or not team.members:
            return None

        active_slot = team.active_slot
        active_member: Optional[LumenMemberState] = None
        for m in team.members:
            if m.slot == active_slot:
                active_member = m
                break

        # Condição de perigo: HP próprio < 25% ou todos os golpes sem PP
        is_hp_critical = telemetry.player_hp_pct < 0.25
        is_pp_depleted = False
        if telemetry.available_moves:
            is_pp_depleted = all(m.current_pp <= 0 for m in telemetry.available_moves)

        if not is_hp_critical and not is_pp_depleted:
            return None

        # Procura melhor substituto saudável
        best_candidate: Optional[LumenMemberState] = None
        best_candidate_hp = 0.0

        for member in team.members:
            if member.slot != active_slot and not member.is_fainted and member.hp_percentage > 0.40:
                if member.hp_percentage > best_candidate_hp:
                    target_id = f"switch_slot_{member.slot}"
                    if target_id not in failed_set:
                        best_candidate = member
                        best_candidate_hp = member.hp_percentage

        if best_candidate is not None:
            score = 90.0 if is_hp_critical else 80.0
            reason = (
                f"HP crítico ({telemetry.player_hp_pct*100:.0f}%) ou PP esgotado. "
                f"Trocando para {best_candidate.nickname} (HP {best_candidate.hp_percentage*100:.0f}%)."
            )

            # Ação de troca: Clica em SWITCH e depois no slot do parceiro
            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_SWITCH", target=f"switch_btn", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=0.4),
                    AtomicAction(action_type="CLICK_SLOT", target=f"team_slot_{best_candidate.slot}", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=0.8),
                ],
                description=f"Trocar Lumen ativo para slot {best_candidate.slot} ({best_candidate.nickname})",
            )

            return ActionDecision(
                action_type="SWITCH",
                target_slot=best_candidate.slot,
                target_name=best_candidate.nickname,
                score=score,
                reason=reason,
                confidence=0.85,
                action_plan=plan,
            )

        return None

    def _evaluate_moves(
        self,
        telemetry: BattleTelemetry,
        team: Optional[TeamStatus],
        failed_set: Set[str],
    ) -> Optional[ActionDecision]:
        """Calcula o score de cada golpe disponível e retorna a melhor decisão."""
        if not telemetry.available_moves:
            return None

        enemy_type1, enemy_type2 = self.infer_enemy_elements(telemetry.enemy_lumen_name)
        candidates: List[ActionDecision] = []

        for move in telemetry.available_moves:
            move_id = f"move_slot_{move.slot_index}"
            score = 0.0
            reason_parts = []

            # 1. Checagem de PP (Inviável se PP == 0)
            if move.current_pp <= 0 or not move.is_available:
                score = -1000.0
                reason_parts.append("Sem PP disponível")
                candidates.append(
                    ActionDecision(
                        action_type="MOVE",
                        target_slot=move.slot_index,
                        target_name=move.name,
                        score=score,
                        reason="; ".join(reason_parts),
                        confidence=0.95,
                    )
                )
                continue

            # 2. Dano Base
            base_power = max(20, move.power)
            score += base_power
            reason_parts.append(f"Poder Base: {base_power}")

            # 3. Multiplicador Elemental (Tabela de 18 tipos)
            mult = get_elemental_multiplier(move.element, enemy_type1, enemy_type2)
            if mult >= 2.0:
                score += 45.0
                reason_parts.append(f"Super Efetivo ({mult}x)")
            elif mult == 0.0:
                score = -500.0
                reason_parts.append("Inimigo Imune (0.0x)")
            elif mult <= 0.5:
                score -= 30.0
                reason_parts.append(f"Pouco Efetivo ({mult}x)")
            else:
                reason_parts.append("Dano Neutro (1.0x)")

            # 4. Oportunidade de Finalização (Kill Shot)
            if telemetry.enemy_hp_pct <= 0.35 and mult >= 1.0:
                score += 30.0
                reason_parts.append(f"Oportunidade de nocaute (HP Oponente {telemetry.enemy_hp_pct*100:.0f}%)")

            # 5. Penalidade para Ações que Falharam Recentemente (Anti-Loop)
            if move_id in failed_set:
                score -= 50.0
                reason_parts.append("Penalidade por falha anterior na mesma ação")

            # Monta ActionPlan concreto com FIGHT e clique no Slot
            plan = ActionPlan(
                actions=[
                    AtomicAction(action_type="CLICK_FIGHT", target="fight_button", duration=0.2),
                    AtomicAction(action_type="WAIT", target="wait", duration=0.3),
                    AtomicAction(
                        action_type="CLICK_MOVE",
                        target=f"slot_{move.slot_index}",
                        duration=0.2,
                    ),
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

        # Retorna o candidato com maior pontuação
        best = max(candidates, key=lambda c: c.score)
        return best

    def _generate_fallback_decision(self, telemetry: BattleTelemetry) -> ActionDecision:
        """Gera ação de avanço seguro quando os slots de ataque ainda não estão visíveis ou percepção está incompleta."""
        # Se posição do botão FIGHT estiver disponível, clica nele
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

        # Caso contrário, clica no centro para avançar animação
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
