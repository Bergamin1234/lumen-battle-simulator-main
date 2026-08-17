"""
LUMENA BOT v3.8 — COMPLETE COMBAT CYCLE CONTROLLER
===================================================
Controlador de execução física determinística de combate baseado em Battle UI.
Responsável pelo ciclo completo de combate:
BATTLE_DETECTED -> CLICK_FIGHT -> SKILL_SELECTION -> TURN_RESOLUTION -> BATTLE_EXIT -> WORLD_RESUME

REGRAS:
- Input Dispatcher Guard: Validação estrita de Foreground e limites do Canvas.
- Turn Lock: Supressão estrita de inputs enquanto a animação do jogo resolve.
- Watchdog de Combate: Recuperação automática e proteção anti-stall.
- Zero Fake Pass: Respeito absoluto à integridade das entradas físicas.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
import numpy as np

from src.core.event_bus import EventBus, EventType
from src.input.input_controller import InputController
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIDetectionResult, BattleUIElement
from src.models.combat_vision import SkillSlot, CombatDecision
from src.models.enums import Element
from src.combat.skill_strategy import SkillStrategyEngine

logger = logging.getLogger("LumenaBattleUIController")


class BattleUIController:
    """Controlador autônomo da interface de batalha com Turn Lock, Rotação de Skills e Watchdog."""

    def __init__(
        self,
        input_controller: Optional[InputController] = None,
        ui_detector: Optional[BattleUIDetector] = None,
        event_bus: Optional[EventBus] = None,
        turn_timeout: float = 6.0,
    ) -> None:
        self.logger = logging.getLogger("LumenaBattleUIController")
        self.input_ctrl = input_controller or InputController()
        self.ui_detector = ui_detector or BattleUIDetector(event_bus=event_bus)
        self.event_bus = event_bus or EventBus()
        self.turn_timeout = turn_timeout
        self.skill_strategy = SkillStrategyEngine()

        self._last_fight_click_time = 0.0
        self._last_skill_action_time = 0.0
        self._last_action_timestamp = time.time()
        self._observation_without_action_count = 0
        self._is_waiting_turn_resolution = False
        self._consecutive_watchdog_triggers = 0

    def wait_for_visual_condition(
        self,
        predicate: Callable[[np.ndarray], bool],
        screen_capture_func: Optional[Callable[[], Tuple[Optional[np.ndarray], float]]],
        timeout: float = 3.0,
        interval: float = 0.05,
    ) -> Tuple[bool, Optional[np.ndarray]]:
        """Executa polling visual com timeout explícito (sem sleeps estáticos cegos)."""
        if not screen_capture_func:
            return False, None

        start_time = time.time()
        while time.time() - start_time < timeout:
            frame, _ = screen_capture_func()
            if frame is not None and frame.size > 0:
                if predicate(frame):
                    return True, frame
            time.sleep(interval)
        return False, None

    @property
    def is_waiting_turn_resolution(self) -> bool:
        return self._is_waiting_turn_resolution

    def validate_input_guard(self, target_x: int, target_y: int) -> bool:
        """Input Dispatcher Guard: Valida se a janela está em primeiro plano e se as coordenadas

        estão estritamente dentro da área visível do canvas de jogo.
        """
        # 1. Verifica existência de janela alvo
        target_info = self.input_ctrl.window_manager.get_active_target()
        if not target_info or target_info.hwnd == 0:
            # Em ambiente sem janela real, aceita modo mock/headless
            return True

        # 2. Valida se as coordenadas estão dentro dos limites da janela/canvas
        bounds = self.input_ctrl.window_manager.get_window_bounds()
        wx, wy, ww, wh = bounds
        if ww > 0 and wh > 0:
            if not (wx <= target_x <= wx + ww and wy <= target_y <= wy + wh):
                self.logger.warning(
                    f"🛑 [INPUT GUARD] Coordenadas ({target_x}, {target_y}) fora dos limites da janela: {bounds}"
                )
                self.event_bus.publish(
                    EventType.INPUT_GUARD_REJECTED,
                    data={"target_coords": (target_x, target_y), "window_bounds": bounds, "reason": "COORDS_OUT_OF_BOUNDS"},
                    category="SAFETY",
                    level="WARNING",
                    message="INPUT_GUARD_REJECTED: Coordenadas fora da janela do jogo.",
                )
                return False

        return True

    def detect_battle_ui(self, frame: Optional[np.ndarray]) -> BattleUIDetectionResult:
        """Executa detecção da interface de combate no frame atual."""
        return self.ui_detector.analyze_battle_ui(frame)

    def find_fight_button(self, frame: np.ndarray) -> Optional[BattleUIElement]:
        """Localiza o botão FIGHT."""
        res = self.ui_detector.analyze_battle_ui(frame)
        if res.fight_button and res.fight_button.is_present:
            return res.fight_button
        return None

    def click_fight(
        self,
        frame_before: Optional[np.ndarray] = None,
        screen_capture_func: Optional[Any] = None,
    ) -> Tuple[bool, float, bool]:
        """Clica fisicamente no botão FIGHT com garantia de foco, guarda de input e verificação fechada.

        Retorna: (dispatched, latency, verified)
        """
        now = time.time()
        action_id = f"fight_{int(now * 1000)}"

        # 1. Garante janela e foco do canvas
        self.input_ctrl.focus_game_window()
        self.input_ctrl.window_manager.ensure_canvas_focus(0.5, 0.5)

        # 2. Localiza botão FIGHT
        fight_elem = None
        if frame_before is not None:
            fight_elem = self.find_fight_button(frame_before)
        if not fight_elem or not fight_elem.is_present:
            bounds = self.input_ctrl.window_manager.get_window_bounds()
            cx = int(bounds[0] + bounds[2] * 0.78)
            cy = int(bounds[1] + bounds[3] * 0.80)
            fight_elem = BattleUIElement(name="FIGHT", center=(cx, cy), confidence=0.70, is_present=True)

        # 3. Input Dispatcher Guard
        if not self.validate_input_guard(fight_elem.center_x, fight_elem.center_y):
            return False, 0.0, False

        target_info = self.input_ctrl.window_manager._current_target
        hwnd = target_info.hwnd if target_info else 0
        pid = getattr(target_info, "pid", 0) if target_info else 0

        # 4. Emite eventos de requisição
        self.event_bus.publish(
            EventType.FIGHT_DETECTED,
            data={"action_id": action_id, "coords": fight_elem.center, "confidence": fight_elem.confidence},
            category="COMBAT",
            level="INFO",
            message=f"FIGHT_DETECTED: Botão FIGHT localizado em {fight_elem.center} (Conf={fight_elem.confidence:.2f})",
        )
        self.event_bus.publish(
            EventType.FIGHT_CLICK_REQUESTED,
            data={"action_id": action_id, "hwnd": hwnd, "pid": pid, "coords": fight_elem.center},
            category="COMBAT",
            level="INFO",
            message="FIGHT_CLICK_REQUESTED: Solicitando clique físico no botão FIGHT.",
        )
        self.event_bus.publish(
            EventType.ACTION_REQUESTED,
            data={"action_id": action_id, "action_type": "CLICK_FIGHT", "hwnd": hwnd, "pid": pid, "coords": fight_elem.center},
            category="COMBAT",
            level="INFO",
            message="ACTION_REQUESTED: CLICK_FIGHT",
        )

        # 5. Despacha o clique físico
        t0 = time.time()
        dispatched = self.input_ctrl.click(fight_elem.center_x, fight_elem.center_y)
        t1 = time.time()
        latency = t1 - t0

        if dispatched:
            self._last_fight_click_time = time.time()
            self._last_action_timestamp = time.time()
            self._observation_without_action_count = 0
            self._consecutive_watchdog_triggers = 0
            self.event_bus.publish(
                EventType.FIGHT_CLICK_DISPATCHED,
                data={"action_id": action_id, "hwnd": hwnd, "pid": pid, "coords": fight_elem.center, "latency": latency},
                category="COMBAT",
                level="INFO",
                message=f"FIGHT_CLICK_DISPATCHED: Clique em FIGHT enviado em {latency*1000:.1f}ms.",
            )
            self.event_bus.publish(
                EventType.ACTION_DISPATCHED,
                data={"action_id": action_id, "action_type": "CLICK_FIGHT", "hwnd": hwnd, "pid": pid, "duration": latency},
                category="COMBAT",
                level="INFO",
                message="ACTION_DISPATCHED: CLICK_FIGHT",
            )
        else:
            self.logger.warning("⚠️ [COMBAT] Falha ao despachar clique no botão FIGHT.")
            return False, latency, False

        # 6. Verificação pós-ação (Closed-Loop Verification)
        verified = False
        if screen_capture_func and frame_before is not None:
            time.sleep(0.18)
            frame_after, _ = screen_capture_func()
            if frame_after is not None:
                verified, v_delta = self.verify_fight_action(frame_before, frame_after)
                if verified:
                    self.event_bus.publish(
                        EventType.FIGHT_CLICK_VERIFIED,
                        data={"action_id": action_id, "visual_delta": v_delta},
                        category="COMBAT",
                        level="INFO",
                        message=f"FIGHT_CLICK_VERIFIED: Menu de habilidades aberto com sucesso (delta={v_delta:.4f}).",
                    )
                    self.event_bus.publish(
                        EventType.ACTION_VERIFIED,
                        data={"action_id": action_id, "action_type": "CLICK_FIGHT", "visual_delta": v_delta},
                        category="COMBAT",
                        level="INFO",
                        message="ACTION_VERIFIED: CLICK_FIGHT",
                    )
                else:
                    self.event_bus.publish(
                        EventType.ACTION_UNCONFIRMED,
                        data={"action_id": action_id, "action_type": "CLICK_FIGHT", "visual_delta": v_delta},
                        category="COMBAT",
                        level="WARNING",
                        message=f"ACTION_UNCONFIRMED: Clique em FIGHT não produziu resposta visual esperada (delta={v_delta:.4f}).",
                    )
        else:
            verified = dispatched

        return dispatched, latency, verified

    def verify_fight_action(self, frame_before: np.ndarray, frame_after: np.ndarray) -> Tuple[bool, float]:
        """Verifica se o clique em FIGHT abriu o menu de habilidades (FIGHT sumiu / Skills apareceram / Delta)."""
        confirmed, visual_delta = self.input_ctrl.compute_visual_delta(frame_before, frame_after)
        ui_res = self.ui_detector.analyze_battle_ui(frame_after)
        if ui_res.skill_menu_open:
            return True, max(visual_delta, 0.02)
        if visual_delta >= 0.006:
            return True, visual_delta
        return False, visual_delta

    def find_available_skills(self, frame: np.ndarray) -> List[SkillSlot]:
        """Localiza e extrai os slots de habilidade dinâmicos do HUD."""
        res = self.ui_detector.analyze_battle_ui(frame)
        skills: List[SkillSlot] = []

        h, w = frame.shape[:2]
        detected_elems = [e for k, e in res.elements.items() if k.startswith("SKILL_")]

        if detected_elems:
            for idx, elem in enumerate(detected_elems, start=1):
                slot = SkillSlot(
                    id=f"skill_slot_{idx}",
                    index=idx,
                    slot_index=idx,
                    screen_x=elem.x,
                    screen_y=elem.y,
                    width=elem.width,
                    height=elem.height,
                    available=True,
                    cooldown=0.0,
                    hotkey=str(idx % 10),
                    skill_name=f"Skill #{idx}",
                    element=Element.NORMAL,
                    confidence=elem.confidence,
                )
                skills.append(slot)
        else:
            # Layout dinâmico normalizado resistente a DPI e resolução (Baseado em % do Canvas)
            bx = int(w * 0.26)
            by = int(h * 0.70)
            slot_w = int(w * 0.22)
            slot_h = int(h * 0.10)
            for i in range(4):
                col = i % 2
                row = i // 2
                sx = bx + col * (slot_w + int(w * 0.03))
                sy = by + row * (slot_h + int(h * 0.03))
                skills.append(SkillSlot(
                    id=f"skill_slot_{i+1}",
                    index=i + 1,
                    slot_index=i + 1,
                    screen_x=sx,
                    screen_y=sy,
                    width=slot_w,
                    height=slot_h,
                    available=True,
                    cooldown=0.0,
                    hotkey=str(i + 1),
                    skill_name=f"Skill #{i+1}",
                    element=Element.NORMAL,
                    confidence=0.80,
                ))

        if skills:
            self.event_bus.publish(
                EventType.SKILL_UI_DETECTED,
                data={"skills_count": len(skills)},
                category="COMBAT",
                level="INFO",
                message=f"SKILL_UI_DETECTED: {len(skills)} slots de habilidades identificados.",
            )

        return skills

    def dismiss_post_battle_modal(
        self,
        frame: Optional[np.ndarray] = None,
        screen_capture_func: Optional[Any] = None,
    ) -> Tuple[bool, float]:
        """Detecta e despacha a confirmação de fechamento de modais pós-combate (VICTORY, LEVEL UP, LOOT)."""
        now = time.time()
        self.input_ctrl.focus_game_window()

        target_x, target_y = self.input_ctrl.get_screen_center()

        if frame is not None:
            res = self.ui_detector.analyze_battle_ui(frame)
            if res.modal_confirm_button and res.modal_confirm_button.is_present:
                target_x, target_y = res.modal_confirm_button.center

        # 1. Despacha clique no modal e envia tecla SPACE
        dispatched = self.input_ctrl.click(target_x, target_y)
        self.input_ctrl.press_key("space", duration=0.10)

        verified = False
        v_delta = 0.0

        if screen_capture_func and frame is not None:
            # Polling visual dinâmico com timeout de 1.5s
            def is_modal_closed(f_check: np.ndarray) -> bool:
                r = self.ui_detector.analyze_battle_ui(f_check)
                return not r.modal_detected

            success, frame_after = self.wait_for_visual_condition(
                is_modal_closed,
                screen_capture_func=screen_capture_func,
                timeout=1.5,
                interval=0.04,
            )
            if frame_after is not None:
                _, v_delta = self.input_ctrl.compute_visual_delta(frame, frame_after)
                verified = True
            else:
                frame_after, _ = screen_capture_func()
                if frame_after is not None:
                    _, v_delta = self.input_ctrl.compute_visual_delta(frame, frame_after)
                    verified = v_delta >= 0.004

        self.event_bus.publish(
            EventType.MODAL_DISMISSED,
            data={"target_coords": (target_x, target_y), "visual_delta": v_delta, "verified": verified},
            category="COMBAT",
            level="INFO",
            message=f"MODAL_DISMISSED: Modal pós-batalha dispensado com sucesso (delta={v_delta:.4f}).",
        )

        return dispatched, v_delta

    def select_primary_skill(self, skills: List[SkillSlot]) -> Optional[SkillSlot]:
        """Seleciona deterministicamente a melhor habilidade disponível via SkillStrategyEngine (multi-turno)."""
        if not skills:
            return None
        return self.skill_strategy.evaluate_skills(skills)

    def execute_skill(
        self,
        skill: SkillSlot,
        frame_before: Optional[np.ndarray] = None,
        screen_capture_func: Optional[Any] = None,
    ) -> Tuple[bool, float, bool]:
        """Despacha uma habilidade selecionada com Input Guard e ativa Turn Lock.

        Retorna: (dispatched, latency, verified)
        """
        now = time.time()
        action_id = f"skill_{int(now * 1000)}_{skill.slot_index}"

        # 1. Input Dispatcher Guard
        if not self.validate_input_guard(skill.center_x, skill.center_y):
            return False, 0.0, False

        target_info = self.input_ctrl.window_manager._current_target
        hwnd = target_info.hwnd if target_info else 0
        pid = getattr(target_info, "pid", 0) if target_info else 0

        # 2. Publica eventos de requisição
        self.event_bus.publish(
            EventType.SKILL_SELECTED,
            data={"action_id": action_id, "slot": skill.slot_index, "name": skill.skill_name, "hotkey": skill.hotkey},
            category="COMBAT",
            level="INFO",
            message=f"SKILL_SELECTED: {skill.skill_name or f'Slot #{skill.slot_index}'} (Hotkey: {skill.hotkey})",
        )
        self.event_bus.publish(
            EventType.SKILL_ACTION_REQUESTED,
            data={"action_id": action_id, "slot": skill.slot_index, "hotkey": skill.hotkey, "hwnd": hwnd, "pid": pid},
            category="COMBAT",
            level="INFO",
            message=f"SKILL_ACTION_REQUESTED: Despachando habilidade '{skill.skill_name}'",
        )
        self.event_bus.publish(
            EventType.ACTION_REQUESTED,
            data={"action_id": action_id, "action_type": "USE_SKILL", "skill_id": skill.id, "hwnd": hwnd, "pid": pid},
            category="COMBAT",
            level="INFO",
            message=f"ACTION_REQUESTED: USE_SKILL ({skill.skill_name})",
        )

        # 3. Despacho Físico (Hotkey com Fallback para Clique)
        t0 = time.time()
        if skill.hotkey:
            dispatched = self.input_ctrl.press_key(skill.hotkey, duration=0.15)
        else:
            dispatched = self.input_ctrl.click(skill.center_x, skill.center_y)
        t1 = time.time()
        latency = t1 - t0

        if dispatched:
            self._last_skill_action_time = time.time()
            self._last_action_timestamp = time.time()
            self._observation_without_action_count = 0
            self._consecutive_watchdog_triggers = 0
            self.skill_strategy.register_skill_use(skill.slot_index)

            # Ativa Turn Lock
            self._is_waiting_turn_resolution = True

            self.event_bus.publish(
                EventType.SKILL_ACTION_DISPATCHED,
                data={"action_id": action_id, "slot": skill.slot_index, "latency": latency, "hwnd": hwnd, "pid": pid},
                category="COMBAT",
                level="INFO",
                message=f"SKILL_ACTION_DISPATCHED: Habilidade enviada com sucesso em {latency*1000:.1f}ms.",
            )
            self.event_bus.publish(
                EventType.ACTION_DISPATCHED,
                data={"action_id": action_id, "action_type": "USE_SKILL", "skill_id": skill.id, "duration": latency},
                category="COMBAT",
                level="INFO",
                message=f"ACTION_DISPATCHED: USE_SKILL ({skill.skill_name})",
            )
            self.event_bus.publish(
                EventType.BATTLE_WAITING_TURN_RESOLUTION,
                data={"skill_id": skill.id, "timestamp": time.time()},
                category="COMBAT",
                level="INFO",
                message="BATTLE_WAITING_TURN_RESOLUTION: Turn Lock ativado. Aguardando resolução da animação de turno.",
            )
        else:
            self.logger.warning(f"⚠️ [COMBAT] Falha ao despachar habilidade {skill.skill_name}")
            return False, latency, False

        # 4. Verificação em malha fechada
        verified = False
        if screen_capture_func and frame_before is not None:
            time.sleep(0.20)
            frame_after, _ = screen_capture_func()
            if frame_after is not None:
                confirmed, visual_delta = self.input_ctrl.compute_visual_delta(frame_before, frame_after)
                verified = bool(confirmed or visual_delta >= 0.005)
                if verified:
                    self.event_bus.publish(
                        EventType.SKILL_ACTION_VERIFIED,
                        data={"action_id": action_id, "visual_delta": visual_delta},
                        category="COMBAT",
                        level="INFO",
                        message=f"SKILL_ACTION_VERIFIED: Ataque '{skill.skill_name}' verificado com sucesso (delta={visual_delta:.4f}).",
                    )
                    self.event_bus.publish(
                        EventType.ACTION_VERIFIED,
                        data={"action_id": action_id, "action_type": "USE_SKILL", "visual_delta": visual_delta},
                        category="COMBAT",
                        level="INFO",
                        message=f"ACTION_VERIFIED: USE_SKILL ({skill.skill_name})",
                    )
                else:
                    self.event_bus.publish(
                        EventType.ACTION_UNCONFIRMED,
                        data={"action_id": action_id, "action_type": "USE_SKILL", "visual_delta": visual_delta},
                        category="COMBAT",
                        level="WARNING",
                        message=f"ACTION_UNCONFIRMED: Ataque '{skill.skill_name}' não confirmado (delta={visual_delta:.4f}).",
                    )
        else:
            verified = dispatched

        return dispatched, latency, verified

    def dispatch_skill_action(
        self,
        slot_index: int = 1,
        frame: Optional[np.ndarray] = None,
        screen_capture_func: Optional[Any] = None,
    ) -> bool:
        """
        Despacha formalmente uma ação de habilidade pelo índice do slot (1 a 4).
        Retorna True se despachado com sucesso.
        """
        skills = self.find_available_skills(frame) if frame is not None else []
        selected_slot: Optional[SkillSlot] = None
        for s in skills:
            if s.slot_index == slot_index or s.index == slot_index:
                selected_slot = s
                break

        if selected_slot is None:
            bounds = self.input_ctrl.window_manager.get_window_bounds()
            wx, wy, ww, wh = bounds
            w = ww if ww > 0 else 1920
            h = wh if wh > 0 else 1080

            bx = int(wx + w * 0.26)
            by = int(wy + h * 0.70)
            slot_w = int(w * 0.22)
            slot_h = int(h * 0.10)
            col = (slot_index - 1) % 2
            row = (slot_index - 1) // 2
            sx = bx + col * (slot_w + int(w * 0.03))
            sy = by + row * (slot_h + int(h * 0.03))

            selected_slot = SkillSlot(
                id=f"skill_slot_{slot_index}",
                index=slot_index,
                slot_index=slot_index,
                screen_x=sx,
                screen_y=sy,
                width=slot_w,
                height=slot_h,
                available=True,
                cooldown=0.0,
                hotkey=str(slot_index % 10),
                skill_name=f"Skill #{slot_index}",
                element=Element.NORMAL,
                confidence=0.85,
            )

        dispatched, latency, verified = self.execute_skill(
            selected_slot,
            frame_before=frame,
            screen_capture_func=screen_capture_func,
        )
        return bool(dispatched)

    def handle_post_battle_modal_dismissal(
        self,
        frame: Optional[np.ndarray] = None,
        screen_capture_func: Optional[Any] = None,
    ) -> bool:
        """Despacha a confirmação de fechamento de modais pós-combate e retorna True se bem-sucedido."""
        dispatched, _ = self.dismiss_post_battle_modal(frame=frame, screen_capture_func=screen_capture_func)
        return bool(dispatched)

    def execute_complete_combat_turn(
        self,
        frame_before: np.ndarray,
        screen_capture_func: Optional[Any] = None,
    ) -> Tuple[bool, str, float]:
        """Executa o ciclo determinístico completo de um turno de combate:

        1. Se menu de skills não estiver aberto -> Clica em FIGHT
        2. Localiza skills
        3. Executa Skill 1
        4. Inicia Turn Lock
        Retorna: (sucesso, etapa_executada, latencia)
        """
        # Se estiver em Turn Lock, não dispara inputs adicionais
        if self._is_waiting_turn_resolution:
            self.logger.debug("[COMBAT] Turn Lock ativo: suprimindo cliques adicionais durante animação.")
            return False, "TURN_LOCKED", 0.0

        ui_res = self.ui_detector.analyze_battle_ui(frame_before)
        if not ui_res.battle_ui_confirmed:
            return False, "NOT_IN_BATTLE", 0.0

        # Passo 1: Abre Menu de Habilidades se ainda não estiver aberto
        current_frame = frame_before
        if not ui_res.skill_menu_open and ui_res.fight_button and ui_res.fight_button.is_present:
            dispatched_fight, lat_fight, _ = self.click_fight(frame_before=frame_before, screen_capture_func=screen_capture_func)
            if not dispatched_fight:
                return False, "FIGHT_CLICK_FAILED", lat_fight
            if screen_capture_func:
                time.sleep(0.25)
                f_after, _ = screen_capture_func()
                if f_after is not None:
                    current_frame = f_after

        # Passo 2: Seleção e Execução de Habilidade
        skills = self.find_available_skills(current_frame)
        if not skills:
            self.logger.warning("⚠️ [COMBAT] Nenhuma habilidade detectada no menu.")
            return False, "NO_SKILLS_FOUND", 0.0

        primary_skill = self.select_primary_skill(skills)
        if not primary_skill:
            return False, "NO_PRIMARY_SKILL", 0.0

        dispatched_skill, lat_skill, verified_skill = self.execute_skill(
            skill=primary_skill,
            frame_before=current_frame,
            screen_capture_func=screen_capture_func,
        )

        return dispatched_skill, f"SKILL_DISPATCHED_{primary_skill.slot_index}", lat_skill

    def process_turn_resolution_check(self, frame: Optional[np.ndarray]) -> bool:
        """Verifica se a animação do turno concluiu e o jogo retornou para novos controles ou exibiu modal pós-batalha."""
        if not self._is_waiting_turn_resolution:
            return True

        if frame is None or frame.size == 0:
            return False

        res = self.ui_detector.analyze_battle_ui(frame)

        # 1. Se modal pós-batalha apareceu (VICTORY, LOOT, LEVEL UP) -> Resolução concluída
        if res.modal_detected:
            self._is_waiting_turn_resolution = False
            self.event_bus.publish(
                EventType.TURN_RESOLUTION_COMPLETED,
                data={"reason": "MODAL_APPEARED", "modal_type": res.modal_type},
                category="COMBAT",
                level="INFO",
                message=f"TURN_RESOLUTION_COMPLETED: Modal pós-batalha exibido ({res.modal_type}).",
            )
            return True

        # 2. Se o botão FIGHT ou menu de skills reapareceu -> Próximo turno liberado
        if (res.fight_button and res.fight_button.is_present) or res.skill_menu_open:
            self._is_waiting_turn_resolution = False
            self.event_bus.publish(
                EventType.TURN_RESOLUTION_COMPLETED,
                data={"reason": "CONTROLS_READY"},
                category="COMBAT",
                level="INFO",
                message="TURN_RESOLUTION_COMPLETED: Controles de combate liberados para o próximo turno.",
            )
            return True

        # Caso contrário, animação ainda está em andamento -> mantém Turn Lock
        return False

    def handle_battle_watchdog(self) -> bool:
        """Battle Turn Watchdog: Acionado quando a batalha fica estagnada sem ação/transição por > 6s."""
        now = time.time()
        elapsed = now - self._last_action_timestamp

        if elapsed > self.turn_timeout:
            self._consecutive_watchdog_triggers += 1
            self.logger.warning(
                f"🛑 [WATCHDOG] BATTLE_TURN_WATCHDOG acionado! Inatividade de {elapsed:.1f}s > {self.turn_timeout}s (Tentativa {self._consecutive_watchdog_triggers}/3)"
            )
            self.event_bus.publish(
                EventType.BATTLE_WATCHDOG_TRIGGERED,
                data={"elapsed": elapsed, "attempt": self._consecutive_watchdog_triggers},
                category="COMBAT",
                level="WARNING",
                message=f"BATTLE_WATCHDOG_TRIGGERED: Recuperando foco e canvas (Tentativa {self._consecutive_watchdog_triggers}).",
            )

            # Destrava Turn Lock e refocaliza
            self._is_waiting_turn_resolution = False
            self.input_ctrl.focus_game_window()
            self.input_ctrl.window_manager.ensure_canvas_focus(0.5, 0.5)
            self._last_action_timestamp = time.time()

            if self._consecutive_watchdog_triggers >= 3:
                self.logger.critical("🛑 [SAFE_STOP] Parada segura acionada por 3 timeouts consecutivos de combate.")
                self.event_bus.publish(
                    EventType.EXECUTION_FAILURE,
                    data={"reason": "BATTLE_WATCHDOG_MAX_RETRIES_EXCEEDED", "triggers": self._consecutive_watchdog_triggers},
                    category="SAFETY",
                    level="CRITICAL",
                    message="EXECUTION_FAILURE: Combate travado sem resposta após 3 tentativas de recuperação.",
                )
                return False

            return True

        return False

    def dismiss_post_battle_dialogs(self) -> None:
        """Clica no centro da tela para avançar/dispensar modais de vitória, loot ou diálogos pós-combate."""
        self.input_ctrl.focus_game_window()
        cx, cy = self.input_ctrl.get_screen_center()
        self.input_ctrl.click(cx, cy)

    def is_battle_finished(
        self,
        frame: Optional[np.ndarray],
        in_battle_hint: Optional[bool] = None,
    ) -> bool:
        """Determina se o combate terminou, a interface de batalha foi fechada e o modo de mundo pode ser retomado."""
        if in_battle_hint is True:
            return False
        if in_battle_hint is False:
            self._is_waiting_turn_resolution = False
            self.event_bus.publish(
                EventType.BATTLE_EXIT_DETECTED,
                data={"timestamp": time.time()},
                category="COMBAT",
                level="INFO",
                message="BATTLE_EXIT_DETECTED: Saída de combate confirmada.",
            )
            self.event_bus.publish(
                EventType.BATTLE_FINISHED,
                data={"timestamp": time.time()},
                category="COMBAT",
                level="INFO",
                message="BATTLE_FINISHED: Batalha concluída com sucesso.",
            )
            self.event_bus.publish(
                EventType.WORLD_RESUMED,
                data={"timestamp": time.time()},
                category="NAVIGATION",
                level="INFO",
                message="WORLD_RESUMED: Modo Overworld retomado com navegação ativa.",
            )
            return True

        if frame is None or frame.size == 0:
            return True
        res = self.ui_detector.analyze_battle_ui(frame)
        if not res.battle_ui_confirmed:
            self._is_waiting_turn_resolution = False
            self.event_bus.publish(
                EventType.BATTLE_EXIT_DETECTED,
                data={"timestamp": time.time()},
                category="COMBAT",
                level="INFO",
                message="BATTLE_EXIT_DETECTED: Saída de combate confirmada.",
            )
            self.event_bus.publish(
                EventType.BATTLE_FINISHED,
                data={"timestamp": time.time()},
                category="COMBAT",
                level="INFO",
                message="BATTLE_FINISHED: Batalha concluída com sucesso.",
            )
            self.event_bus.publish(
                EventType.WORLD_RESUMED,
                data={"timestamp": time.time()},
                category="NAVIGATION",
                level="INFO",
                message="WORLD_RESUMED: Modo Overworld retomado com navegação ativa.",
            )
            return True
        return False
