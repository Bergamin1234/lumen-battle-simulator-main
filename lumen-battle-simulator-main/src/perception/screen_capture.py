import time
import logging
import threading
from typing import Optional, Tuple, Dict
import cv2
import numpy as np
import mss


class ScreenCapture:
    """Captura concorrente e de alta performance de frames de tela usando MSS com caching e diff temporal."""

    def __init__(
        self,
        monitor_index: int = 1,
        capture_region: Optional[Dict[str, int]] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        self.monitor_index = monitor_index
        self.capture_region = capture_region  # {"top": int, "left": int, "width": int, "height": int}
        self._sct: Optional[mss.mss] = None
        self._lock = threading.Lock()

        self._current_frame: Optional[np.ndarray] = None
        self._previous_frame: Optional[np.ndarray] = None
        self._current_timestamp: float = 0.0
        self._motion_energy: float = 0.0
        self.current_canvas_bounds: Tuple[int, int, int, int] = (0, 0, 1920, 1080)
        self.zoom_factor: float = 1.0
        self.is_letterboxed: bool = False

    @property
    def sct(self) -> mss.mss:
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def detect_webgl_canvas_bounds(self, raw_frame: Optional[np.ndarray] = None) -> Tuple[int, int, int, int]:
        """
        Escaneia o frame da janela descartando barras pretas puras (Letterboxing/Pillarboxing)
        e bordas de interface de navegador para isolar o retângulo ativo do Canvas WebGL.
        Retorna (canvas_x, canvas_y, canvas_w, canvas_h).
        """
        frame = raw_frame if raw_frame is not None else self._current_frame
        if frame is None or frame.size == 0:
            return self.current_canvas_bounds

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

        # Identifica linhas e colunas não-pretas (threshold > 15 para tolerar leve ruído)
        row_mask = np.max(gray, axis=1) > 15
        col_mask = np.max(gray, axis=0) > 15

        row_indices = np.where(row_mask)[0]
        col_indices = np.where(col_mask)[0]

        if len(row_indices) == 0 or len(col_indices) == 0:
            # Tela preta completa ou inválida
            return 0, 0, w, h

        top = int(row_indices[0])
        bottom = int(row_indices[-1])
        left = int(col_indices[0])
        right = int(col_indices[-1])

        canvas_w = max(1, right - left + 1)
        canvas_h = max(1, bottom - top + 1)

        # Se cobrir > 98% da tela, considera tela cheia sem letterbox
        is_letterboxed = (canvas_w < w * 0.98) or (canvas_h < h * 0.98)
        self.is_letterboxed = is_letterboxed
        self.current_canvas_bounds = (left, top, canvas_w, canvas_h)

        # Estima fator de escala relativo a 1080p
        self.zoom_factor = round(canvas_w / 1920.0, 3) if canvas_w > 0 else 1.0
        return self.current_canvas_bounds

    def map_normalized_roi_to_canvas(
        self,
        roi_norm: Tuple[float, float, float, float],
        frame_shape: Optional[Tuple[int, int]] = None,
    ) -> Tuple[int, int, int, int]:
        """
        Mapeia uma ROI normalizada (nx, ny, nw, nh entre 0.0 e 1.0) estritamente
        para as coordenadas absolutas dentro do Canvas WebGL detectado.
        """
        cx, cy, cw, ch = self.current_canvas_bounds
        if frame_shape and (cw == 0 or ch == 0):
            h, w = frame_shape
            cx, cy, cw, ch = 0, 0, w, h

        nx, ny, nw, nh = roi_norm
        rx = int(cx + nx * cw)
        ry = int(cy + ny * ch)
        rw = int(nw * cw)
        rh = int(nh * ch)
        return rx, ry, rw, rh

    def set_capture_region(self, region: Optional[Dict[str, int]]) -> None:
        with self._lock:
            self.capture_region = region

    def get_monitor_resolution(self) -> Tuple[int, int]:
        """Retorna (largura, altura) do monitor configurado."""
        try:
            if 0 <= self.monitor_index < len(self.sct.monitors):
                mon = self.sct.monitors[self.monitor_index]
                return mon["width"], mon["height"]
        except Exception as e:
            self.logger.debug(f"Erro ao obter resolução do monitor: {e}")
        return 1920, 1080

    def capture_frame(self) -> Tuple[Optional[np.ndarray], float]:
        """
        Captura o frame atual de tela de forma thread-safe.
        Retorna (frame_bgr, timestamp).
        """
        timestamp = time.time()
        with self._lock:
            try:
                if self.capture_region:
                    box = self.capture_region
                else:
                    if self.monitor_index < len(self.sct.monitors):
                        box = self.sct.monitors[self.monitor_index]
                    else:
                        box = self.sct.monitors[0]

                sct_img = self.sct.grab(box)
                frame_bgra = np.array(sct_img, dtype=np.uint8)
                frame_bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
                del sct_img
                del frame_bgra

                self._previous_frame = self._current_frame
                self._current_frame = frame_bgr
                self._current_timestamp = timestamp

                if self._previous_frame is not None and self._previous_frame.shape == self._current_frame.shape:
                    self._motion_energy = self.compute_frame_diff(self._previous_frame, self._current_frame)
                else:
                    self._motion_energy = 0.0

                return frame_bgr, timestamp
            except Exception as e:
                self.logger.debug(f"Aviso durante captura MSS: {e}")
                try:
                    if self._sct is not None:
                        self._sct.close()
                except Exception:
                    pass
                self._sct = None
                return None, timestamp

    @staticmethod
    def compute_frame_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
        """
        Calcula a diferença normalizada (0.0 a 1.0) entre dois frames.
        Utiliza downsampling para desempenho em tempo real.
        """
        if frame1 is None or frame2 is None or frame1.shape != frame2.shape:
            return 0.0

        try:
            # Reduz resolução para cálculo rápido de energia de movimento
            small1 = cv2.resize(frame1, (160, 90), interpolation=cv2.INTER_AREA)
            small2 = cv2.resize(frame2, (160, 90), interpolation=cv2.INTER_AREA)

            gray1 = cv2.cvtColor(small1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(small2, cv2.COLOR_BGR2GRAY)

            diff = cv2.absdiff(gray1, gray2)
            mean_diff = float(np.mean(diff))
            # Normalização (255 max grayscale diff)
            return min(1.0, mean_diff / 255.0)
        except Exception:
            return 0.0

    def get_last_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._current_frame.copy() if self._current_frame is not None else None

    def get_last_timestamp(self) -> float:
        with self._lock:
            return self._current_timestamp

    def get_motion_energy(self) -> float:
        with self._lock:
            return self._motion_energy

    def close(self) -> None:
        with self._lock:
            if self._sct is not None:
                try:
                    self._sct.close()
                except Exception:
                    pass
                self._sct = None
