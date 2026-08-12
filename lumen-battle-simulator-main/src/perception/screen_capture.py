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

    @property
    def sct(self) -> mss.mss:
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

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

                self._previous_frame = self._current_frame
                self._current_frame = frame_bgr
                self._current_timestamp = timestamp

                if self._previous_frame is not None and self._previous_frame.shape == self._current_frame.shape:
                    self._motion_energy = self.compute_frame_diff(self._previous_frame, self._current_frame)
                else:
                    self._motion_energy = 0.0

                return frame_bgr, timestamp
            except Exception as e:
                self.logger.error(f"Erro durante captura de tela MSS: {e}")
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
