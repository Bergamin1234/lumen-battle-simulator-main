import time
import logging
from typing import Optional, Dict
import numpy as np

from src.models.enums import AgentState
from src.models.lumen import StateSnapshot, BattleTelemetry, UIElement, PlayerInfo, TargetLockInfo
from src.perception.ui_detector import UIDetector
from src.perception.battle_detector import BattleDetector
from src.perception.world_detector import WorldDetector
from src.perception.landmark_detector import LandmarkDetector
from src.perception.ocr import OCREngine


class StateClassifier:
    """Classificador semântico multimodal que integra todos os detectores e sintetiza o StateSnapshot."""

    def __init__(
        self,
        ui_detector: Optional[UIDetector] = None,
        battle_detector: Optional[BattleDetector] = None,
        world_detector: Optional[WorldDetector] = None,
        landmark_detector: Optional[LandmarkDetector] = None,
        ocr_engine: Optional[OCREngine] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        self.ui_detector = ui_detector or UIDetector()
        self.battle_detector = battle_detector or BattleDetector()
        self.world_detector = world_detector or WorldDetector()
        self.landmark_detector = landmark_detector or LandmarkDetector()
        self.ocr_engine = ocr_engine or OCREngine()

        self._previous_state: AgentState = AgentState.INACTIVE

    def classify_frame(
        self,
        frame: Optional[np.ndarray],
        timestamp: Optional[float] = None,
        motion_energy: float = 0.0,
    ) -> StateSnapshot:
        """Processa um frame de vídeo e sintetiza o StateSnapshot consistente."""
        ts = timestamp if timestamp is not None else time.time()

        if frame is None or frame.size == 0:
            return StateSnapshot(
                timestamp=ts,
                screen_state=AgentState.UNKNOWN_STATE,
                ui_elements={},
                battle_telemetry=BattleTelemetry(in_battle=False),
                crystal_detected=False,
                crystal_relative_pos=None,
                grass_density=0.0,
                motion_energy=0.0,
                player_info=PlayerInfo(detected=False),
            )

        try:
            # 1. Executa detecção de UI
            ui_elements = self.ui_detector.detect_all(frame)

            # 2. Executa detecção do Jogador (Player)
            p_found, p_bbox, p_center, p_conf = self.landmark_detector.detect_player(frame)
            player_info = PlayerInfo(
                x=p_bbox[0],
                y=p_bbox[1],
                center=p_center,
                bounding_box=p_bbox,
                confidence=p_conf,
                detected=p_found,
            )
            if p_found:
                ui_elements["player"] = UIElement(
                    name="player",
                    bounding_box=p_bbox,
                    confidence=p_conf,
                    center=p_center,
                    semantic_type="PLAYER",
                )

            # 3. Executa detecção de Batalha
            battle_telemetry = self.battle_detector.detect_battle_state(frame)

            # 4. Executa detecção do Mundo e Vegetação
            world_features = self.world_detector.detect_world_features(frame)
            grass_density = world_features["grass_density"]

            # 5. Executa detecção de Marcos (Cristal Azul de Cura relativo ao Jogador)
            crystal_found, crystal_pos, crystal_elem = self.landmark_detector.detect_crystal(frame, player_pos=p_center)
            if crystal_found and crystal_elem is not None:
                ui_elements["blue_crystal"] = crystal_elem

            # 6. Classificação Semântica do Estado do Agente
            state = self._determine_agent_state(
                ui_elements=ui_elements,
                battle_telemetry=battle_telemetry,
                grass_density=grass_density,
                crystal_detected=crystal_found,
                motion_energy=motion_energy,
            )

            self._previous_state = state

            return StateSnapshot(
                timestamp=ts,
                screen_state=state,
                ui_elements=ui_elements,
                battle_telemetry=battle_telemetry,
                crystal_detected=crystal_found,
                crystal_relative_pos=crystal_pos,
                grass_density=grass_density,
                motion_energy=motion_energy,
                player_info=player_info,
            )

        except Exception as e:
            self.logger.error(f"Erro inesperado no StateClassifier: {e}")
            return StateSnapshot(
                timestamp=ts,
                screen_state=AgentState.UNKNOWN_STATE,
                ui_elements={},
                battle_telemetry=BattleTelemetry(in_battle=False),
                crystal_detected=False,
                crystal_relative_pos=None,
                grass_density=0.0,
                motion_energy=motion_energy,
                player_info=PlayerInfo(detected=False),
            )

    def _determine_agent_state(
        self,
        ui_elements: Dict[str, UIElement],
        battle_telemetry: BattleTelemetry,
        grass_density: float,
        crystal_detected: bool,
        motion_energy: float,
    ) -> AgentState:
        """Lógica hierárquica de determinação do estado cognitivo."""
        # A. Tela preta / Loading
        if "black_screen" in ui_elements:
            return AgentState.CALIBRATING

        # B. Batalha e Resultados de Combate
        if battle_telemetry.in_battle:
            if battle_telemetry.victory_detected or battle_telemetry.defeat_detected:
                return AgentState.BATTLE_RESULT
            if self._previous_state not in (AgentState.BATTLE, AgentState.BATTLE_DETECTED, AgentState.SWITCHING_LUMEN):
                return AgentState.BATTLE_DETECTED
            return AgentState.BATTLE

        # C. Diálogo com o Cristal de Cura
        has_dialog = "dialog_box" in ui_elements
        if has_dialog and crystal_detected:
            return AgentState.HEALING

        # D. Cristal Azul no Campo Visual
        if crystal_detected:
            return AgentState.SEARCHING_CRYSTAL

        # E. Exploração no Mato (Grama Alta)
        if grass_density >= 0.08:
            return AgentState.EXPLORING

        # F. Busca por Área de Farm / Caminhos
        if grass_density < 0.08:
            return AgentState.SEARCHING_FARM

        # Fallback seguro para Exploração
        return AgentState.EXPLORING
