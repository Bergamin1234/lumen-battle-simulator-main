"""
LUMENA BOT CONTROL CENTER v4.3 — BLACKBOX SESSION REPLAY VIEWER
==============================================================
Mecanismo de inspeção e reprodução quadro a quadro dos dumps forenses gravados
pelo Blackbox Flight Recorder (debug/blackbox/<timestamp>_<reason>/).
Permite reprodução interativa, avanço/recuo de passos e sincronização com telemetria.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
import cv2
import numpy as np

logger = logging.getLogger("LumenaReplayViewer")


class BlackboxReplayEngine:
    """Motor de reprodução e inspeção de dados de voo forenses do Blackbox."""

    def __init__(self, dump_dir: Optional[str] = None) -> None:
        self.logger = logging.getLogger("LumenaReplayViewer")
        self.dump_dir: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self.snapshots: List[Dict[str, Any]] = []
        self.frame_paths: List[str] = []
        self.current_frame_idx: int = 0
        self.is_playing: bool = False
        self.playback_speed: float = 1.0  # 1x, 0.5x, 2x

        if dump_dir and os.path.exists(dump_dir):
            self.load_dump_directory(dump_dir)

    def list_available_dumps(self, base_dir: str = "debug/blackbox") -> List[str]:
        """Lista todas as pastas de dumps forenses disponíveis em ordem cronológica reversa."""
        if not os.path.exists(base_dir):
            return []
        entries = []
        for d in os.listdir(base_dir):
            full_path = os.path.join(base_dir, d)
            if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, "flight_data.json")):
                entries.append(full_path)
        entries.sort(reverse=True)
        return entries

    def load_dump_directory(self, dump_dir: str) -> bool:
        """Carrega e valida a integridade de uma pasta de dump do Blackbox."""
        if not os.path.exists(dump_dir):
            self.logger.error(f"Pasta de dump não encontrada: {dump_dir}")
            return False

        json_path = os.path.join(dump_dir, "flight_data.json")
        if not os.path.exists(json_path):
            self.logger.error(f"flight_data.json ausente em: {dump_dir}")
            return False

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.metadata = {
                "timestamp": data.get("dump_timestamp") or data.get("timestamp"),
                "reason": data.get("dump_reason") or data.get("reason"),
                "total_snapshots": data.get("total_snapshots", 0),
            }
            self.snapshots = data.get("timeline") or data.get("snapshots", [])

            # Localiza os arquivos de thumbnail de frame correspondentes (.jpg ou .png)
            self.frame_paths = []
            for i in range(len(self.snapshots)):
                fp = ""
                for candidate_name in (
                    f"frame_{i + 1:03d}.jpg",
                    f"frame_{i + 1:03d}.png",
                    f"frame_{i:03d}.jpg",
                    f"frame_{i:03d}.png",
                ):
                    test_fp = os.path.join(dump_dir, candidate_name)
                    if os.path.exists(test_fp):
                        fp = test_fp
                        break
                self.frame_paths.append(fp)

            self.dump_dir = dump_dir
            self.current_frame_idx = 0
            self.is_playing = False
            self.logger.info(f"✓ [REPLAY] Dump carregado: {dump_dir} ({len(self.snapshots)} frames).")
            return True
        except Exception as e:
            self.logger.error(f"Falha ao carregar dump {dump_dir}: {e}")
            return False

    def get_total_frames(self) -> int:
        return len(self.snapshots)

    def seek(self, index: int) -> bool:
        """Move o ponteiro de reprodução para o índice especificado."""
        if 0 <= index < len(self.snapshots):
            self.current_frame_idx = index
            return True
        return False

    def step_forward(self) -> bool:
        """Avança 1 quadro."""
        if self.current_frame_idx < len(self.snapshots) - 1:
            self.current_frame_idx += 1
            return True
        else:
            self.is_playing = False
            return False

    def step_backward(self) -> bool:
        """Recua 1 quadro."""
        if self.current_frame_idx > 0:
            self.current_frame_idx -= 1
            return True
        return False

    def play(self) -> None:
        self.is_playing = True

    def pause(self) -> None:
        self.is_playing = False

    def toggle_play(self) -> bool:
        self.is_playing = not self.is_playing
        return self.is_playing

    def get_current_snapshot_data(self) -> Dict[str, Any]:
        """Retorna os dados do quadro atual com imagem e metadados sincronizados."""
        if not self.snapshots or self.current_frame_idx >= len(self.snapshots):
            return {
                "index": 0,
                "frame": None,
                "state": "NONE",
                "last_input": "NONE",
                "events": [],
                "extra": {},
            }

        snap = self.snapshots[self.current_frame_idx]
        frame_img = None

        if self.current_frame_idx < len(self.frame_paths):
            fp = self.frame_paths[self.current_frame_idx]
            if fp and os.path.exists(fp):
                frame_img = cv2.imread(fp)

        return {
            "index": self.current_frame_idx,
            "total_frames": len(self.snapshots),
            "timestamp": snap.get("timestamp"),
            "state": snap.get("state", "UNKNOWN"),
            "last_input": snap.get("last_input", "NONE"),
            "events": snap.get("events", []),
            "extra_metrics": snap.get("extra_metrics", {}),
            "frame": frame_img,
            "is_playing": self.is_playing,
        }
