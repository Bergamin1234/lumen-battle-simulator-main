"""
LUMENA BOT v3.9 — GLOBAL EMERGENCY KILLSWITCH
==============================================
Sistema de interrupção de emergência em nível de hardware/OS.
Monitora hotkeys de pânico (F12 / ESC mantido) e força liberação de inputs e transição para SAFE_STOP.
"""

import os
import sys
import time
import json
import logging
import threading
from typing import Optional, Callable, Dict, Any

from src.core.event_bus import EventBus, EventType
from src.automation.state_machine import BotState, BotStateMachine

logger = logging.getLogger("LumenaKillswitch")


class EmergencyKillswitch:
    """Killswitch assíncrono global com liberação física de teclas e dump de emergência."""

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        state_machine: Optional[BotStateMachine] = None,
        release_keys_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaKillswitch")
        self.event_bus = event_bus or EventBus()
        self.state_machine = state_machine
        self.release_keys_callback = release_keys_callback
        self._is_active = False
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._triggered = False

    @property
    def is_triggered(self) -> bool:
        return self._triggered

    def start_listening(self) -> None:
        """Inicia o listener em thread secundária."""
        if self._listener_thread and self._listener_thread.is_alive():
            return
        self._stop_event.clear()
        self._triggered = False
        self._is_active = True
        self._listener_thread = threading.Thread(target=self._monitor_hotkeys, daemon=True, name="KillswitchMonitor")
        self._listener_thread.start()
        self.logger.info("🛡️ [KILLSWITCH] Monitor de emergência ativo (Hotkey: F12 / ESC).")

    def stop_listening(self) -> None:
        """Encerra o listener de forma limpa."""
        self._stop_event.set()
        self._is_active = False
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=0.2)

    def clear_all_virtual_key_states(self) -> int:
        """Libera fisicamente todas as teclas virtuais no Win32 para evitar teclas presas."""
        released_count = 0
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                KEYEVENTF_KEYUP = 0x0002

                common_vks = [
                    0x57, 0x41, 0x53, 0x44,  # W, A, S, D
                    0x20, 0x0D, 0x1B, 0x09,  # SPACE, ENTER, ESC, TAB
                    0x10, 0x11, 0x12,        # SHIFT, CTRL, ALT
                    0x25, 0x26, 0x27, 0x28,  # LEFT, UP, RIGHT, DOWN
                    0x31, 0x32, 0x33, 0x34,  # 1, 2, 3, 4
                    0x45, 0x46,              # E, F
                ]
                for vk in common_vks:
                    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                    released_count += 1
            except Exception as e:
                self.logger.debug(f"[Killswitch] Erro na liberação Win32: {e}")
        return released_count

    def _monitor_hotkeys(self) -> None:
        """Loop de monitoramento de teclas de pânico via Win32 GetAsyncKeyState."""
        VK_F12 = 0x7B
        VK_ESCAPE = 0x1B

        esc_press_start = 0.0

        while not self._stop_event.is_set():
            try:
                # Checa se ctypes/user32 está acessível
                if sys.platform == "win32":
                    import ctypes
                    user32 = ctypes.windll.user32

                    # Checa F12 (bit mais significativo indica tecla pressionada)
                    f12_state = user32.GetAsyncKeyState(VK_F12) & 0x8000
                    if f12_state:
                        self.trigger_emergency_stop(reason="HOTKEY_F12_PRESSED")
                        break

                    # Checa ESC mantido por > 1.0s
                    esc_state = user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000
                    if esc_state:
                        if esc_press_start == 0.0:
                            esc_press_start = time.time()
                        elif time.time() - esc_press_start >= 1.0:
                            self.trigger_emergency_stop(reason="HOTKEY_ESC_HELD_1S")
                            break
                    else:
                        esc_press_start = 0.0

                time.sleep(0.05)
            except Exception as e:
                self.logger.debug(f"[Killswitch] Erro na leitura de teclas: {e}")
                time.sleep(0.1)

    def trigger_emergency_stop(self, reason: str = "MANUAL_KILLSWITCH") -> None:
        """Dispara a rotina imediata de parada de emergência e segurança de input."""
        self._triggered = True
        now = time.time()
        self.logger.critical(f"🛑🛑🛑 [KILLSWITCH ACIONADO] Motivo: {reason} 🛑🛑🛑")

        # 1. Liberação física completa de todas as teclas virtuais no Win32
        self.clear_all_virtual_key_states()
        if self.release_keys_callback:
            try:
                self.release_keys_callback()
            except Exception as e:
                self.logger.error(f"[Killswitch] Erro ao liberar teclas via callback: {e}")

        # 2. Transição da Máquina de Estados para SAFE_STOP
        if self.state_machine:
            try:
                self.state_machine.transition_to(BotState.SAFE_STOP, reason=f"KILLSWITCH: {reason}")
            except Exception as e:
                self.logger.error(f"[Killswitch] Erro na transição de FSM: {e}")

        # 3. Publicação de eventos de emergência
        self.event_bus.publish(
            EventType.KILLSWITCH_TRIGGERED,
            data={"reason": reason, "timestamp": now},
            category="SAFETY",
            level="CRITICAL",
            message=f"KILLSWITCH_TRIGGERED: Parada imediata solicitada ({reason}).",
        )
        self.event_bus.publish(
            EventType.SAFE_STOP_TRIGGERED,
            data={"reason": reason, "timestamp": now},
            category="SAFETY",
            level="CRITICAL",
            message="SAFE_STOP_TRIGGERED: Entradas suspensas e robô em parada segura.",
        )
        self.event_bus.publish(
            EventType.EMERGENCY_STOP,
            data={"reason": reason, "timestamp": now},
            category="SAFETY",
            level="CRITICAL",
            message="EMERGENCY_STOP: Aborto global ativo.",
        )

        # 4. Dump de telemetria de emergência
        try:
            out_dir = os.path.abspath("debug")
            os.makedirs(out_dir, exist_ok=True)
            dump_path = os.path.join(out_dir, "emergency_stop.json")
            dump_data = {
                "timestamp": now,
                "reason": reason,
                "triggered": True,
                "state": self.state_machine.current_state.name if self.state_machine else "UNKNOWN",
            }
            with open(dump_path, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"📁 Dump de emergência salvo em: {dump_path}")
        except Exception as e:
            self.logger.error(f"[Killswitch] Erro ao salvar dump: {e}")

    def reset(self) -> None:
        """Reseta o estado do killswitch."""
        self._triggered = False
        self._stop_event.clear()
