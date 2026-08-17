"""
LUMENA BOT v4.4 — COMPACT JPEG BLACKBOX FLIGHT RECORDER (IN-MEMORY RING BUFFER)
==============================================================================
Gravador de voo circular em RAM para diagnóstico forense de anomalias:
- Mantém em memória os últimos 15 segundos de operação contínua (150 snapshots @ 10Hz)
- Compactação JPEG em tempo real (Qualidade 70) -> Consumo de RAM < 5 MB para 150 frames
- Zero overhead de I/O em disco durante a operação nominal
- Auto-dump instantâneo em diretório de evidência em caso de travamento, stall ou safe-stop
"""

import os
import time
import json
import logging
import collections
from typing import Dict, List, Optional, Any, Deque, Tuple
import numpy as np
import cv2


class BlackboxSnapshot:
    """Snapshot atômico de telemetria e percepção em memória com compressão JPEG."""
    __slots__ = ("timestamp", "state_name", "frame_jpeg", "last_input", "events", "extra_metrics")

    def __init__(
        self,
        timestamp: float,
        state_name: str,
        frame_jpeg: Optional[bytes],
        last_input: str,
        events: List[Dict[str, Any]],
        extra_metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.timestamp = timestamp
        self.state_name = state_name
        self.frame_jpeg = frame_jpeg
        self.last_input = last_input
        self.events = events
        self.extra_metrics = extra_metrics or {}

    def get_frame(self) -> Optional[np.ndarray]:
        """Decodifica sob demanda a imagem comprimida em JPEG."""
        if self.frame_jpeg is not None and len(self.frame_jpeg) > 0:
            try:
                buf = np.frombuffer(self.frame_jpeg, dtype=np.uint8)
                return cv2.imdecode(buf, cv2.IMREAD_COLOR)
            except Exception:
                return None
        return None

    @property
    def frame_thumb(self) -> Optional[np.ndarray]:
        """Propriedade para compatibilidade retroativa com código legado."""
        return self.get_frame()


class BlackboxFlightRecorder:
    """Gravador circular de alta performance em memória (< 5 MB RAM para 150 snapshots compactados)."""

    def __init__(self, buffer_size: int = 150) -> None:
        self.logger = logging.getLogger("LumenaBlackbox")
        self.buffer_size = buffer_size
        self._ring_buffer: Deque[BlackboxSnapshot] = collections.deque(maxlen=buffer_size)
        self._is_dumping = False

    def record_step(
        self,
        frame: Optional[np.ndarray],
        state_name: str,
        last_input: str = "",
        events: Optional[List[Dict[str, Any]]] = None,
        extra_metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Adiciona um snapshot no buffer circular comprimindo o frame em JPEG na RAM."""
        now = time.time()
        jpeg_bytes: Optional[bytes] = None
        if frame is not None and frame.size > 0:
            try:
                # 1. Reduz para 480x270 (16:9 preview)
                thumb = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_AREA)
                # 2. Comprime em JPEG qualidade 65 (~10KB a 18KB por quadro)
                success, encoded = cv2.imencode(".jpg", thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                if success:
                    jpeg_bytes = encoded.tobytes()
            except Exception as e:
                self.logger.debug(f"Erro na compressão JPEG do Blackbox: {e}")
                jpeg_bytes = None

        snap = BlackboxSnapshot(
            timestamp=now,
            state_name=state_name,
            frame_jpeg=jpeg_bytes,
            last_input=last_input,
            events=list(events) if events else [],
            extra_metrics=extra_metrics or {},
        )
        self._ring_buffer.append(snap)

    def get_snapshot_count(self) -> int:
        """Retorna o número de snapshots atualmente em memória."""
        return len(self._ring_buffer)

    def get_estimated_ram_usage_mb(self) -> float:
        """Calcula o uso real estimado de RAM do buffer circular em megabytes."""
        total_bytes = 0
        for snap in self._ring_buffer:
            if snap.frame_jpeg:
                total_bytes += len(snap.frame_jpeg)
            total_bytes += 256  # Overhead de metadados
        return round(total_bytes / (1024.0 * 1024.0), 3)

    def clear(self) -> None:
        """Limpa o buffer circular."""
        self._ring_buffer.clear()

    def get_snapshot(self, index: int) -> Optional[BlackboxSnapshot]:
        """Obtém o snapshot no índice especificado."""
        if 0 <= index < len(self._ring_buffer):
            return self._ring_buffer[index]
        return None

    def dump_blackbox(
        self,
        reason: str = "CRASH_DUMP",
        base_dir: str = "debug/blackbox",
    ) -> Optional[str]:
        """
        Despeja instantaneamente a sequência dos últimos 15 segundos em disco.
        Gera flight_data.json e frames de evidência.
        """
        if self._is_dumping or not self._ring_buffer:
            return None

        self._is_dumping = True
        try:
            ts_str = time.strftime("%Y%m%d_%H%M%S")
            sanitized_reason = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in reason)
            dump_dir = os.path.abspath(os.path.join(base_dir, f"{ts_str}_{sanitized_reason}"))
            os.makedirs(dump_dir, exist_ok=True)

            flight_records = []
            snapshots = list(self._ring_buffer)

            for i, snap in enumerate(snapshots):
                record = {
                    "index": i + 1,
                    "timestamp": snap.timestamp,
                    "state": snap.state_name,
                    "last_input": snap.last_input,
                    "events_count": len(snap.events),
                    "events": snap.events,
                    "metrics": snap.extra_metrics,
                }
                flight_records.append(record)

                if snap.frame_jpeg is not None:
                    frame_img = snap.get_frame()
                    if frame_img is not None:
                        frame_fname = f"frame_{i + 1:03d}.png"
                        cv2.imwrite(os.path.join(dump_dir, frame_fname), frame_img)
                    else:
                        frame_fname = f"frame_{i + 1:03d}.jpg"
                        with open(os.path.join(dump_dir, frame_fname), "wb") as f_img:
                            f_img.write(snap.frame_jpeg)

            with open(os.path.join(dump_dir, "flight_data.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "dump_reason": reason,
                        "dump_timestamp": time.time(),
                        "total_snapshots": len(flight_records),
                        "timeline": flight_records,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            self.logger.critical(f"📁 [BLACKBOX] Dump forense gerado com sucesso em: {dump_dir} ({self.get_estimated_ram_usage_mb():.2f} MB)")
            return dump_dir
        except Exception as e:
            self.logger.error(f"Erro ao gerar dump do Blackbox: {e}")
            return None
        finally:
            self._is_dumping = False
