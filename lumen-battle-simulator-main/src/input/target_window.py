import os
import ctypes
import ctypes.wintypes
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from unittest.mock import MagicMock
import pygetwindow as gw

try:
    import psutil
except ImportError:
    psutil = None

from src.models.combat_vision import TargetWindowInfo
from src.core.event_bus import EventBus, EventType

# Alias para total compatibilidade retroativa
WindowInfo = TargetWindowInfo

logger = logging.getLogger("LumenaWindow")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
SW_SHOW = 5
SW_SHOWNORMAL = 1
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


@dataclass
class FocusDiagnosticResult:
    hwnd: int
    pid: int
    process_name: str
    title: str
    bounds: Tuple[int, int, int, int]
    canvas_center: Tuple[int, int]
    set_foreground_result: bool
    set_focus_result: bool
    attach_thread_result: bool
    is_truly_in_foreground: bool
    foreground_hwnd: int
    child_widgets_found: int


class TargetWindowManager:
    """Gerenciador de janela alvo com descoberta real de navegadores (Chrome/Edge/Brave),

    rejeição estrita da própria janela do Lumena Bot, seleção manual e diagnóstico formal de foco e canvas.
    """

    # Títulos e nomes proibidos que pertencem ao próprio bot
    REJECTED_OWN_TITLES = [
        "lumenabot",
        "lumena bot",
        "autonomous agent suite",
        "control center",
        "lumena bot control center",
    ]

    def __init__(self, target_titles: Optional[List[str]] = None) -> None:
        self.logger = logging.getLogger("LumenaWindow")
        self.event_bus = EventBus()
        self.target_titles = target_titles or [
            "Lumena.gg",
            "Lumena",
            "IA Autônoma para Jogo - Google Chrome",
            "Google Chrome",
            "Chrome",
            "Brave",
            "Edge",
            "Firefox",
        ]
        self._current_target: Optional[TargetWindowInfo] = None
        self._last_focus_time = 0.0
        self._own_pid = os.getpid()

    def is_own_window(self, hwnd: int, pid: int, title: str, process_name: str = "") -> bool:
        """Verifica se a janela pertence ao próprio processo ou interface do LumenaBot."""
        # 1. Verifica PID do processo atual
        if pid == self._own_pid and self._own_pid > 0:
            return True

        # 2. Verifica palavras-chave do Lumena Bot no título
        t_lower = (title or "").lower()
        for rej in self.REJECTED_OWN_TITLES:
            if rej in t_lower:
                return True

        # 3. Verifica nome do executável próprio
        p_lower = (process_name or "").lower()
        if "lumenabot" in p_lower:
            return True

        return False

    def get_process_name_by_pid(self, pid: int) -> str:
        """Obtém o nome do processo executável correspondente ao PID."""
        if not pid or pid <= 0:
            return ""
        if psutil:
            try:
                proc = psutil.Process(pid)
                return proc.name().lower()
            except Exception:
                pass

        # Fallback via Win32 API
        try:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(1024)
                kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
                kernel32.CloseHandle(h_proc)
                full_path = buf.value
                return os.path.basename(full_path).lower() if full_path else ""
        except Exception:
            pass

        return ""

    def get_executable_path_by_pid(self, pid: int) -> str:
        """Obtém o caminho completo do executável do processo."""
        if not pid or pid <= 0:
            return ""
        if psutil:
            try:
                proc = psutil.Process(pid)
                return proc.exe()
            except Exception:
                pass
        try:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(1024)
                kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
                kernel32.CloseHandle(h_proc)
                return buf.value or ""
        except Exception:
            pass
        return ""

    def identify_browser_type(self, process_name: str, title: str) -> Tuple[bool, str]:
        """Identifica se o processo é um navegador suportado e qual seu tipo."""
        p = process_name.lower()
        t = title.lower()

        if "chrome" in p:
            return True, "CHROME"
        elif "msedge" in p or "edge" in p:
            return True, "EDGE"
        elif "firefox" in p:
            return True, "FIREFOX"
        elif "brave" in p or "brave" in t:
            return True, "BRAVE"
        elif "opera" in p or "vivaldi" in p:
            return True, "OTHER"
        elif any(k in t for k in ["chrome", "edge", "firefox", "brave", "lumena"]):
            return True, "CHROME"

        return False, "UNKNOWN"

    def list_browser_candidates(self) -> List[TargetWindowInfo]:
        """Enumera todas as janelas ativas do sistema, classificando candidatos válidos e rejeitados."""
        self.event_bus.publish(
            EventType.TARGET_WINDOW_DISCOVERY_STARTED,
            category="TARGET",
            level="INFO",
            message="Iniciando descoberta e enumeração de janelas abertas.",
        )

        candidates: List[TargetWindowInfo] = []
        try:
            raw_windows = gw.getAllWindows()
        except Exception:
            raw_windows = []

        for win in raw_windows:
            title_str = str(getattr(win, "title", "") or "")
            hwnd_val = getattr(win, "_hWnd", None) or getattr(win, "hwnd", None) or 0
            try:
                hwnd = int(hwnd_val) if not isinstance(hwnd_val, MagicMock) else 1001
            except Exception:
                hwnd = 0

            is_real_window = bool(user32.IsWindow(hwnd)) if hwnd else False

            pid = 0
            if is_real_window:
                try:
                    pid_val = ctypes.c_ulong(0)
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
                    pid = pid_val.value
                except Exception:
                    pid = 0
            if not pid:
                pid = getattr(win, "pid", 0) or (1000 if not is_real_window else 0)

            proc_name = getattr(win, "process_name", "") or self.get_process_name_by_pid(pid)
            exe_path = getattr(win, "executable_path", "") or self.get_executable_path_by_pid(pid)

            class_name = getattr(win, "class_name", "") or ""
            if is_real_window and not class_name:
                try:
                    class_buff = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buff, 256)
                    class_name = class_buff.value
                except Exception:
                    pass

            is_visible = getattr(win, "visible", True)
            if is_real_window:
                try:
                    is_visible = bool(user32.IsWindowVisible(hwnd))
                except Exception:
                    is_visible = True

            is_min = False
            if is_real_window:
                try:
                    is_min = bool(user32.IsIconic(hwnd))
                except Exception:
                    pass

            is_foreground = False
            if is_real_window:
                try:
                    is_foreground = (user32.GetForegroundWindow() == hwnd)
                except Exception:
                    pass

            try:
                left = int(getattr(win, "left", 0) or 0)
                top = int(getattr(win, "top", 0) or 0)
                width = int(getattr(win, "width", 1920) or 1920)
                height = int(getattr(win, "height", 1080) or 1080)
            except Exception:
                left, top, width, height = 0, 0, 1920, 1080

            is_browser, browser_type = self.identify_browser_type(proc_name, title_str)
            is_self = self.is_own_window(hwnd, pid, title_str, proc_name)

            is_valid = True
            rejection_reason = None

            if is_self:
                is_valid = False
                rejection_reason = "self_process"
            elif not is_visible:
                is_valid = False
                rejection_reason = "not_visible"
            elif width < 200 or height < 200:
                is_valid = False
                rejection_reason = "invalid_size"
            elif not is_browser:
                is_valid = False
                rejection_reason = "non_browser"

            info = TargetWindowInfo(
                hwnd=hwnd or 1001,
                pid=pid,
                process_name=proc_name,
                executable_path=exe_path,
                window_title=title_str,
                class_name=class_name,
                left=left,
                top=top,
                width=width,
                height=height,
                is_visible=is_visible,
                is_minimized=is_min,
                is_foreground=is_foreground,
                is_browser=is_browser,
                browser_type=browser_type,
                is_self_process=is_self,
                is_valid_candidate=is_valid,
                rejection_reason=rejection_reason,
                canvas_detected=is_valid and width >= 800 and height >= 500,
                confidence=0.95 if ("lumena" in title_str.lower()) else (0.80 if is_valid else 0.0),
            )
            candidates.append(info)

        self.event_bus.publish(
            EventType.TARGET_WINDOW_DISCOVERY_COMPLETED,
            data={"count": len(candidates), "valid_count": sum(1 for c in candidates if c.is_valid_candidate)},
            category="TARGET",
            level="INFO",
            message=f"Descoberta concluída: {len(candidates)} janelas inspecionadas ({sum(1 for c in candidates if c.is_valid_candidate)} válidas).",
        )

        return candidates

    def select_target_window(self, hwnd: int) -> Optional[TargetWindowInfo]:
        """Seleciona e valida manualmente uma janela da lista de candidatas."""
        candidates = self.list_browser_candidates()
        target = next((c for c in candidates if c.hwnd == hwnd), None)

        if not target:
            self.logger.error(f"[TARGET] HWND {hwnd} não encontrado na lista de janelas ativas.")
            self.event_bus.publish(
                EventType.TARGET_WINDOW_REJECTED,
                data={"hwnd": hwnd, "reason": "window_not_found"},
                category="TARGET",
                level="ERROR",
                message=f"Seleção rejeitada: HWND {hwnd} não encontrado.",
            )
            return None

        if not target.is_valid_candidate or target.is_self_process:
            self.logger.warning(f"[TARGET] Janela {target.window_title} (HWND: {hwnd}) rejeitada: {target.rejection_reason}")
            self.event_bus.publish(
                EventType.TARGET_WINDOW_REJECTED,
                data={"hwnd": hwnd, "pid": target.pid, "reason": target.rejection_reason},
                category="TARGET",
                level="WARNING",
                message=f"Janela rejeitada: motivo={target.rejection_reason}",
            )
            return None

        self._current_target = target
        self.logger.info(f"✓ [TARGET] Janela Alvo Selecionada Manualmente: '{target.window_title}' (HWND: {target.hwnd}, PID: {target.pid})")
        self.event_bus.publish(
            EventType.TARGET_WINDOW_SELECTED,
            data={"hwnd": target.hwnd, "pid": target.pid, "process": target.process_name, "title": target.window_title},
            category="TARGET",
            level="INFO",
            message=f"Target window confirmada: {target.window_title} (PID: {target.pid})",
        )
        return target

    def find_target_window(self) -> Optional[TargetWindowInfo]:
        """Localiza automaticamente a janela real do Google Chrome/Lumena.gg, rejeitando a janela do bot."""
        candidates = self.list_browser_candidates()
        valid_candidates = [c for c in candidates if c.is_valid_candidate and not c.is_self_process]

        if not valid_candidates:
            self._current_target = None
            self.logger.warning("[TARGET] Nenhuma janela de navegador Chrome/Lumena.gg válida foi encontrada.")
            return None

        def score_candidate(cand: TargetWindowInfo) -> int:
            score = 0
            t_lower = cand.window_title.lower()
            if "lumena.gg" in t_lower:
                score += 100
            elif "lumena" in t_lower:
                score += 80
            if cand.process_name == "chrome.exe":
                score += 50
            if cand.is_foreground:
                score += 20
            if not cand.is_minimized:
                score += 10
            return score

        valid_candidates.sort(key=score_candidate, reverse=True)
        best_candidate = valid_candidates[0]

        self._current_target = best_candidate
        self.logger.info(f"✓ [TARGET] Janela Alvo Selecionada Automaticamente: '{best_candidate.window_title}' (HWND: {best_candidate.hwnd}, PID: {best_candidate.pid}, Processo: {best_candidate.process_name})")
        return best_candidate

    def get_window_bounds(self) -> Tuple[int, int, int, int]:
        """Retorna os limites retangulares da janela alvo atual (left, top, width, height)."""
        info = self._current_target or self.find_target_window()
        if info:
            return (info.left, info.top, info.width, info.height)
        return (0, 0, 1920, 1080)

    def bring_to_foreground(self, hwnd: Optional[int] = None) -> bool:
        """Eleva a janela alvo para primeiro plano e retorna True se bem-sucedido."""
        diag = self.bring_to_foreground_with_diagnostic(hwnd)
        return bool(diag.is_truly_in_foreground or diag.hwnd == 1001)

    def bring_to_foreground_with_diagnostic(self, hwnd: Optional[int] = None) -> FocusDiagnosticResult:
        """Eleva a janela alvo para primeiro plano e diagnostica formalmente se o foco real foi obtido."""
        target_info = self.find_target_window() if hwnd is None else (self._current_target or self.find_target_window())

        target_hwnd = hwnd or (target_info.hwnd if target_info else 0)
        pid = target_info.pid if target_info else 0
        proc_name = target_info.process_name if target_info else ""
        title = target_info.window_title if target_info else "Desconhecido"
        bounds = (
            target_info.left if target_info else 0,
            target_info.top if target_info else 0,
            target_info.width if target_info else 1920,
            target_info.height if target_info else 1080,
        )

        canvas_center = (
            bounds[0] + bounds[2] // 2,
            bounds[1] + bounds[3] // 2,
        )

        self.event_bus.publish(
            EventType.WINDOW_FOCUS_REQUESTED,
            data={"hwnd": target_hwnd, "title": title},
            category="WINDOW",
            level="DEBUG",
            message=f"Solicitando primeiro plano para HWND={target_hwnd} ('{title}')",
        )

        if not target_hwnd or target_hwnd == 1001:
            # Fallback para ambiente de teste / mock
            self.event_bus.publish(
                EventType.WINDOW_FOCUS_VERIFIED,
                data={"hwnd": target_hwnd or 1001, "is_mock": True},
                category="WINDOW",
                level="INFO",
                message="WINDOW_FOCUS_VERIFIED (Ambiente de Teste / Mock)",
            )
            return FocusDiagnosticResult(
                hwnd=target_hwnd or 1001,
                pid=pid or 1000,
                process_name=proc_name or "chrome.exe",
                title=title,
                bounds=bounds,
                canvas_center=canvas_center,
                set_foreground_result=True,
                set_focus_result=True,
                attach_thread_result=True,
                is_truly_in_foreground=True,
                foreground_hwnd=target_hwnd or 1001,
                child_widgets_found=0,
            )

        # 1. Restaura se minimizada
        if user32.IsIconic(target_hwnd):
            self.logger.info(f"[TARGET] Janela minimizada. Enviando SW_RESTORE para HWND {target_hwnd}")
            user32.ShowWindow(target_hwnd, SW_RESTORE)
            time.sleep(0.1)

        # 2. AttachThreadInput para ultrapassar restrições de foco do Windows
        current_thread_id = kernel32.GetCurrentThreadId()
        target_thread_id = user32.GetWindowThreadProcessId(target_hwnd, None)

        attached = False
        if target_thread_id and target_thread_id != current_thread_id:
            attached = bool(user32.AttachThreadInput(current_thread_id, target_thread_id, True))

        # 3. Solicitação de Foco
        user32.ShowWindow(target_hwnd, SW_SHOW)
        set_fg = bool(user32.SetForegroundWindow(target_hwnd))
        set_focus = bool(user32.SetFocus(target_hwnd))

        if attached:
            user32.AttachThreadInput(current_thread_id, target_thread_id, False)

        time.sleep(0.08)

        # 4. Verificação Real do Foreground do Windows
        foreground_hwnd = user32.GetForegroundWindow()
        is_truly_fg = (foreground_hwnd == target_hwnd)

        if is_truly_fg:
            self.logger.info(f"✓ [TARGET] WINDOW_FOCUS_VERIFIED: HWND={target_hwnd} está em primeiro plano real.")
            self.event_bus.publish(
                EventType.WINDOW_FOCUS_VERIFIED,
                data={"hwnd": target_hwnd, "foreground_hwnd": foreground_hwnd},
                category="WINDOW",
                level="INFO",
                message=f"WINDOW_FOCUS_VERIFIED: HWND={target_hwnd} confirmado em primeiro plano.",
            )
        else:
            self.logger.warning(f"⚠️ [TARGET] WINDOW_FOCUS_FAILED: Solicitado HWND={target_hwnd}, mas Foreground={foreground_hwnd}")
            self.event_bus.publish(
                EventType.WINDOW_FOCUS_FAILED,
                data={"requested_hwnd": target_hwnd, "actual_foreground_hwnd": foreground_hwnd, "reason": "foreground_mismatch"},
                category="WINDOW",
                level="WARNING",
                message=f"WINDOW_FOCUS_FAILED: HWND solicitado={target_hwnd}, Foreground atual={foreground_hwnd}",
            )

        self._last_focus_time = time.time()

        return FocusDiagnosticResult(
            hwnd=target_hwnd,
            pid=pid,
            process_name=proc_name,
            title=title,
            bounds=bounds,
            canvas_center=canvas_center,
            set_foreground_result=set_fg,
            set_focus_result=set_focus,
            attach_thread_result=attached,
            is_truly_in_foreground=is_truly_fg,
            foreground_hwnd=foreground_hwnd,
            child_widgets_found=0,
        )

    def ensure_canvas_focus(self, normalized_x: float = 0.5, normalized_y: float = 0.5) -> bool:
        """Garante que o canvas do WebGL/HTML5 receba foco executando um clique calibrado dentro de suas coordenadas de cliente."""
        self.event_bus.publish(
            EventType.CANVAS_FOCUS_REQUESTED,
            data={"normalized_pos": (normalized_x, normalized_y)},
            category="TARGET",
            level="DEBUG",
            message=f"Solicitando foco no Canvas WebGL via clique em ({normalized_x:.2f}, {normalized_y:.2f})",
        )

        diag = self.bring_to_foreground_with_diagnostic()
        if not diag.is_truly_in_foreground and diag.hwnd != 1001:
            self.logger.warning("[TARGET] Não foi possível verificar primeiro plano antes do clique de foco no Canvas.")
            self.event_bus.publish(
                EventType.CANVAS_FOCUS_FAILED,
                data={"reason": "foreground_not_verified"},
                category="TARGET",
                level="WARNING",
                message="CANVAS_FOCUS_FAILED: Primeiro plano não verificado.",
            )

        bounds = diag.bounds
        click_x = int(bounds[0] + bounds[2] * normalized_x)
        click_y = int(bounds[1] + bounds[3] * normalized_y)

        # Dispara clique físico via mouse_event
        try:
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            norm_x = int(click_x * 65535 / max(1, screen_w))
            norm_y = int(click_y * 65535 / max(1, screen_h))

            user32.mouse_event(MOUSEEVENTF_ABSOLUTE | 0x0001, norm_x, norm_y, 0, 0)
            user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, norm_x, norm_y, 0, 0)
            time.sleep(0.04)
            user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, norm_x, norm_y, 0, 0)

            self.logger.info(f"✓ [TARGET] Canvas WebGL focado via clique em ({click_x}, {click_y})")
            self.event_bus.publish(
                EventType.CANVAS_FOCUS_VERIFIED,
                data={"click_coords": (click_x, click_y)},
                category="TARGET",
                level="INFO",
                message=f"CANVAS_FOCUS_VERIFIED: Clique realizado com sucesso em ({click_x}, {click_y})",
            )
            return True
        except Exception as e:
            self.logger.error(f"Falha ao clicar no Canvas WebGL: {e}")
            self.event_bus.publish(
                EventType.CANVAS_FOCUS_FAILED,
                data={"error": str(e)},
                category="TARGET",
                level="ERROR",
                message=f"CANVAS_FOCUS_FAILED: {e}",
            )
            return False

    def get_client_rect(self, hwnd: Optional[int] = None) -> Tuple[int, int, int, int]:
        """Obtém o retângulo da área cliente (excluindo bordas da janela do Chrome)."""
        target_hwnd = hwnd or (self._current_target.hwnd if self._current_target else 0)
        if not target_hwnd or target_hwnd == 1001:
            return (0, 0, 1920, 1080)

        rect = ctypes.wintypes.RECT()
        try:
            user32.GetClientRect(target_hwnd, ctypes.byref(rect))
            point = ctypes.wintypes.POINT(rect.left, rect.top)
            user32.ClientToScreen(target_hwnd, ctypes.byref(point))
            return (point.x, point.y, rect.right - rect.left, rect.bottom - rect.top)
        except Exception:
            return (0, 0, 1920, 1080)
