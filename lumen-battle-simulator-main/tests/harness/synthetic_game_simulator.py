"""
LUMENA BOT v4.0 — SYNTHETIC REAL-TIME GAME SIMULATOR (CI HARNESS)
==================================================================
Simulador em memória para validação ponta a ponta do ciclo de vida autônomo completo:
WORLD (100% HP) -> BATTLE (FIGHT) -> SKILLS (SLOT ROTATION) -> TURN LOCK ->
VICTORY MODAL -> WORLD (30% HP) -> HEALING (CRISTAL) -> WORLD (100% HP).
"""

import time
import numpy as np
import cv2
from typing import List, Tuple, Optional, Dict, Any

from src.models.enums import AgentState
from src.automation.state_machine import BotState


class SyntheticGameSimulator:
    """Simulador sintético gerador de frames e telemetria para CI determinístico."""

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        self.width = width
        self.height = height
        self.current_step = 0
        self.player_hp_ratio = 1.0

    def reset(self) -> None:
        self.current_step = 0
        self.player_hp_ratio = 1.0

    def generate_frame_for_step(self, step: int) -> Tuple[np.ndarray, str]:
        """Gera frame sintético realista baseado na fase do ciclo autônomo."""
        self.current_step = step
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # FASE 1: Explorando Mundo Aberto (100% HP) - Passos 1 a 5
        if 1 <= step <= 5:
            self.player_hp_ratio = 1.0
            # Fundo de mapa/terreno verde
            frame[:, :] = (34, 139, 34)
            # Personagem no centro
            cv2.circle(frame, (self.width // 2, self.height // 2), 25, (255, 255, 255), -1)
            # HUD de vida no canto superior/inferior esquerdo
            cv2.rectangle(frame, (50, 50), (250, 75), (0, 0, 0), -1)
            cv2.rectangle(frame, (52, 52), (248, 73), (0, 220, 0), -1)
            return frame, "WORLD_HEALTHY"

        # FASE 2: Entrada na Arena de Batalha (Botão FIGHT) - Passos 6 a 10
        elif 6 <= step <= 10:
            # Fundo de arena de combate
            frame[:, :] = (40, 40, 60)
            # Inimigo no topo direito
            cv2.rectangle(frame, (800, 150), (1050, 350), (60, 60, 200), -1)
            # Barra de vida do inimigo
            cv2.rectangle(frame, (800, 120), (1050, 135), (0, 0, 255), -1)
            # Jogador na base esquerda
            cv2.circle(frame, (350, 500), 40, (200, 200, 200), -1)
            # Botão FIGHT no canto inferior direito
            cv2.rectangle(frame, (950, 560), (1180, 640), (20, 30, 220), -1)  # Botão FIGHT
            return frame, "BATTLE_FIGHT"

        # FASE 3: Menu de Habilidades Aberto (4 slots) - Passos 11 a 15
        elif 11 <= step <= 15:
            frame[:, :] = (40, 40, 60)
            cv2.rectangle(frame, (800, 150), (1050, 350), (60, 60, 200), -1)
            # 4 Slots de Habilidade no terço inferior
            bx, by = int(self.width * 0.26), int(self.height * 0.70)
            sw, sh = int(self.width * 0.22), int(self.height * 0.10)
            for i in range(4):
                col = i % 2
                row = i // 2
                sx = bx + col * (sw + int(self.width * 0.03))
                sy = by + row * (sh + int(self.height * 0.03))
                cv2.rectangle(frame, (sx, sy), (sx + sw, sy + sh), (180, 120, 50), -1)
            return frame, "BATTLE_SKILLS"

        # FASE 4: Resolução de Turno (Animação de Dano / Turn Lock) - Passos 16 a 20
        elif 16 <= step <= 20:
            frame[:, :] = (50, 30, 70)
            # Efeito de ataque / animação
            cv2.circle(frame, (925, 250), 60 + (step - 16) * 10, (0, 255, 255), -1)
            return frame, "BATTLE_ANIMATION"

        # FASE 5: Modal de Vitória Pós-Combate (VICTORY / OK) - Passos 21 a 25
        elif 21 <= step <= 25:
            frame[:, :] = (30, 30, 30)
            # Caixa modal no centro
            cv2.rectangle(frame, (400, 200), (880, 520), (220, 220, 220), -1)
            # Botão OK / Confirmar
            cv2.rectangle(frame, (540, 440), (740, 490), (50, 180, 50), -1)
            return frame, "VICTORY_MODAL"

        # FASE 6: Retorno ao Mundo Aberto com HP Crítico (30%) - Passos 26 a 30
        elif 26 <= step <= 30:
            self.player_hp_ratio = 0.30
            frame[:, :] = (34, 139, 34)
            cv2.circle(frame, (self.width // 2, self.height // 2), 25, (255, 255, 255), -1)
            # Barra de vida vermelha / baixa (30%)
            cv2.rectangle(frame, (50, 50), (250, 75), (0, 0, 0), -1)
            cv2.rectangle(frame, (52, 52), (52 + int(196 * 0.30), 73), (0, 0, 220), -1)
            # Cristal azul visível no horizonte
            cv2.rectangle(frame, (700, 250), (800, 400), (220, 150, 20), -1)
            return frame, "WORLD_LOW_HP"

        # FASE 7: Cura no Cristal e Restauração para 100% HP - Passos 31 a 35
        else:
            self.player_hp_ratio = 1.0
            frame[:, :] = (34, 139, 34)
            # Personagem interagindo com o cristal
            cv2.rectangle(frame, (self.width // 2 - 20, self.height // 2 - 40), (self.width // 2 + 60, self.height // 2 + 60), (220, 180, 40), -1)
            # Barra de vida restaurada para 100%
            cv2.rectangle(frame, (50, 50), (250, 75), (0, 0, 0), -1)
            cv2.rectangle(frame, (52, 52), (248, 73), (0, 220, 0), -1)
            return frame, "WORLD_HEALED"
