"""
LUMENA BOT CONTROL CENTER v4.3 — SELF-HEALING RUNTIME DAEMON
============================================================
Motor de auto-recuperação contínua para anomalias de desktop e navegador:
1. Perda de Foco Crítica (Restabelecimento seguro antes de despachar inputs).
2. Janela Minimizada / Oculta (Restauração via Win32 ShowWindow e recalibração).
3. Congelamento de Frame WebGL (Detecção de estagnação de quadros e despertar via micro-movimento).
4. Auto-Dismiss de Popups Inesperados (Fechamento automático de caixas intrusivas).
"""

import time
import ctypes
import logging
from typing import Optional, List, Tuple, Deque, Any
from collections import deque
import numpy as np
import cv2

from src.core.event_bus import EventBus, EventType
from src.input.target_window import TargetWindowManager

logger = logging.getLogger("LumenaSelfHealing")
user32 = ctypes.windll.user32
SW_RESTORE = 9


class SelfHealingEngine:
    """Daemon de resiliência e auto-recuperação em tempo de execução."""

    def __init__(
        self,
        window_manager: Optional[TargetWindowManager] = None,
        input_controller: Optional[Any] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaSelfHealing")
        self.win_mgr = window_manager or TargetWindowManager()
        self.input_ctrl = input_controller
        self.event_bus = event_bus or EventBus()

        self._frame_variance_history: Deque[float] = deque(maxlen=10)
        self._last_unfreeze_attempt = 0.0
        self._freeze_recovery_count = 0

    def recover_lost_foreground(self, target_hwnd: int) -> bool:
        """Verifica se a janela perdeu foco e executa reaquisição forçada antes de qualquer input."""
        if not target_hwnd or target_hwnd <= 0:
            return False

        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd == target_hwnd:
            return True

        self.logger.warning(f"⚠️ [SELF-HEALING] Janela alvo (HWND {target_hwnd}) perdeu foco para HWND {fg_hwnd}. Restaurando...")
        self.event_bus.publish(
            EventType.WINDOW_FOCUS_REQUESTED,
            data={"target_hwnd": target_hwnd, "current_fg": fg_hwnd},
            category="SELF_HEALING",
            level="WARNING",
            message="Foco do SO perdido. Requisitando reaquisição...",
        )

        ok = self.win_mgr.ensure_foreground(target_hwnd)
        time.sleep(0.1)
        new_fg = user32.GetForegroundWindow()
        restored = (new_fg == target_hwnd) or ok

        if restored:
            self.logger.info(f"✓ [SELF-HEALING] Foco restaurado com sucesso para HWND {target_hwnd}.")
            self.event_bus.publish(
                EventType.WINDOW_FOCUS_VERIFIED,
                data={"hwnd": target_hwnd},
                category="SELF_HEALING",
                level="INFO",
                message="Foco restaurado com sucesso.",
            )
        else:
            self.logger.error(f"✗ [SELF-HEALING] Falha ao recuperar foco da janela HWND {target_hwnd}.")

        return restored

    def recover_minimized_window(self, target_hwnd: int) -> bool:
        """Detecta se a janela está minimizada (IsIconic) e restaura seu estado visível."""
        if not target_hwnd or target_hwnd <= 0:
            return False

        if user32.IsIconic(target_hwnd):
            self.logger.warning(f"⚠️ [SELF-HEALING] Janela HWND {target_hwnd} está minimizada. Executando ShowWindow(SW_RESTORE)...")
            user32.ShowWindow(target_hwnd, SW_RESTORE)
            time.sleep(0.2)
            self.win_mgr.ensure_foreground(target_hwnd)

            self.event_bus.publish(
                EventType.WINDOW_RESTORED,
                data={"hwnd": target_hwnd},
                category="SELF_HEALING",
                level="INFO",
                message="Janela restaurada do estado minimizado.",
            )
            return True
        return False

    def detect_and_recover_webgl_freeze(self, frame: np.ndarray) -> bool:
        """Calcula variância temporal de frames. Se congelado (<0.001), despacha micro-evento para reativar WebGL."""
        if frame is None or frame.size == 0:
            return False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        var = float(np.var(gray))
        self._frame_variance_history.append(var)

        # Se houver 10 amostras e a diferença máxima for insignificante (< 0.0005)
        if len(self._frame_variance_history) >= 10:
            diff = max(self._frame_variance_history) - min(self._frame_variance_history)
            if diff < 0.0005:
                now = time.time()
                if now - self._last_unfreeze_attempt > 4.0:
                    self._last_unfreeze_attempt = now
                    self._freeze_recovery_count += 1
                    self.logger.warning(f"❄️ [SELF-HEALING] Congelamento visual de WebGL detectado (diff={diff:.6f}). Despachando micro-estímulo...")
                    self.event_bus.publish(
                        EventType.WEBGL_FRAME_FREEZE_DETECTED,
                        data={"variance_diff": diff, "recovery_count": self._freeze_recovery_count},
                        category="SELF_HEALING",
                        level="WARNING",
                        message="WebGL Frame Freeze detectado. Reativando ciclo de eventos.",
                    )

                    # Micro-movimento do mouse ou clique neutro no centro do canvas
                    if self.input_ctrl:
                        self.input_ctrl.move_to(960, 540)
                        time.sleep(0.05)
                        self.input_ctrl.move_to(962, 542)
                    return True
        return False

    def auto_dismiss_unexpected_popups(self, frame: np.ndarray) -> bool:
        """Detecta popups intrusivos (extensões, tradução, alertas de permissão) e envia ESC."""
        if frame is None or frame.size == 0:
            return False

        h, w = frame.shape[:2]
        # Região superior direita (popups típicos do Chrome)
        top_right_roi = frame[0:int(h * 0.20), int(w * 0.70):w]
        if top_right_roi.size > 0:
            gray = cv2.cvtColor(top_right_roi, cv2.COLOR_BGR2GRAY)
            # Se houver uma caixa contrastante clara/branca típica de popover
            white_pixels = np.sum(gray > 230)
            if white_pixels > (top_right_roi.shape[0] * top_right_roi.shape[1] * 0.15):
                self.logger.info("🛡️ [SELF-HEALING] Possível popup intrusivo detectado no quadrante superior. Enviando ESC...")
                if self.input_ctrl:
                    self.input_ctrl.press_key("esc", duration=0.1)
                self.event_bus.publish(
                    EventType.POPUP_DISMISSED,
                    data={"region": "top_right"},
                    category="SELF_HEALING",
                    level="INFO",
                    message="Popup intrusivo dispensado via tecla ESC.",
                )
                return True
        return False
