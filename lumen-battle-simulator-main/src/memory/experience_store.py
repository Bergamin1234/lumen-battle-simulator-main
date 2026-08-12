import os
import time
import sqlite3
import logging
from typing import Dict, List, Optional, Set, Tuple, Any


class ExperienceStore:
    """Armazenamento persistente leve baseado em SQLite para marcos, heatmap, histórico de stuck e métricas."""

    def __init__(self, db_path: str = "config/experience.db") -> None:
        self.logger = logging.getLogger("LumenaMemory")
        self.db_path = db_path
        self._session_id = f"session_{int(time.time())}"
        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Retorna a conexão configurada com timeout e row_factory."""
        if self._conn is None:
            if self.db_path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


    def _init_database(self) -> None:
        """Cria as tabelas do banco de dados de forma tolerante a falhas."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_metadata (
                        session_id TEXT PRIMARY KEY,
                        start_time REAL,
                        end_time REAL,
                        total_steps INTEGER DEFAULT 0,
                        battles_won INTEGER DEFAULT 0,
                        battles_lost INTEGER DEFAULT 0,
                        heals_completed INTEGER DEFAULT 0
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS landmarks (
                        name TEXT PRIMARY KEY,
                        world_x REAL,
                        world_y REAL,
                        confidence REAL,
                        times_seen INTEGER DEFAULT 1,
                        last_seen_ts REAL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS exploration_grid (
                        cell_x INTEGER,
                        cell_y INTEGER,
                        visit_count INTEGER DEFAULT 1,
                        is_obstacle INTEGER DEFAULT 0,
                        last_visited_ts REAL,
                        PRIMARY KEY (cell_x, cell_y)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stuck_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        pos_x REAL,
                        pos_y REAL,
                        action_attempted TEXT,
                        resolved INTEGER DEFAULT 0
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS action_outcomes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        action_type TEXT,
                        target TEXT,
                        success INTEGER
                    )
                    """
                )
                # Registra início da sessão atual
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO session_metadata (session_id, start_time, total_steps, battles_won, battles_lost, heals_completed)
                    VALUES (?, ?, 0, 0, 0, 0)
                    """,
                    (self._session_id, time.time()),
                )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Erro ao inicializar ExperienceStore SQLite ({self.db_path}): {e}")

    # -------------------------------------------------------------
    # Persistência de Landmarks
    # -------------------------------------------------------------
    def save_landmark(self, name: str, world_x: float, world_y: float, confidence: float = 1.0) -> None:
        """Salva ou atualiza um landmark conhecido."""
        try:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO landmarks (name, world_x, world_y, confidence, times_seen, last_seen_ts)
                    VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        world_x = excluded.world_x,
                        world_y = excluded.world_y,
                        confidence = excluded.confidence,
                        times_seen = times_seen + 1,
                        last_seen_ts = excluded.last_seen_ts
                    """,
                    (name, float(world_x), float(world_y), float(confidence), now),
                )
                conn.commit()
        except Exception as e:
            self.logger.debug(f"Aviso ao salvar landmark: {e}")

    def load_landmarks(self) -> List[Dict[str, Any]]:
        """Carrega todos os landmarks persistidos."""
        landmarks = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, world_x, world_y, confidence, times_seen, last_seen_ts FROM landmarks")
                for row in cursor.fetchall():
                    landmarks.append(
                        {
                            "name": row["name"],
                            "world_x": row["world_x"],
                            "world_y": row["world_y"],
                            "confidence": row["confidence"],
                            "times_seen": row["times_seen"],
                            "last_seen_ts": row["last_seen_ts"],
                        }
                    )
        except Exception as e:
            self.logger.debug(f"Aviso ao carregar landmarks: {e}")
        return landmarks

    # -------------------------------------------------------------
    # Persistência de Heatmap e Obstáculos
    # -------------------------------------------------------------
    def save_exploration_cell(
        self,
        cell_x: int,
        cell_y: int,
        visits: int,
        is_obstacle: bool = False,
    ) -> None:
        """Salva ou atualiza uma célula do grid de exploração."""
        try:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO exploration_grid (cell_x, cell_y, visit_count, is_obstacle, last_visited_ts)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(cell_x, cell_y) DO UPDATE SET
                        visit_count = excluded.visit_count,
                        is_obstacle = excluded.is_obstacle,
                        last_visited_ts = excluded.last_visited_ts
                    """,
                    (int(cell_x), int(cell_y), int(visits), 1 if is_obstacle else 0, now),
                )
                conn.commit()
        except Exception as e:
            self.logger.debug(f"Aviso ao salvar célula de exploração: {e}")

    def load_exploration_grid(self) -> Dict[Tuple[int, int], int]:
        """Carrega o mapa de calor persistido."""
        grid: Dict[Tuple[int, int], int] = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cell_x, cell_y, visit_count FROM exploration_grid")
                for row in cursor.fetchall():
                    grid[(row["cell_x"], row["cell_y"])] = row["visit_count"]
        except Exception as e:
            self.logger.debug(f"Aviso ao carregar exploration_grid: {e}")
        return grid

    def load_obstacles(self) -> Set[Tuple[int, int]]:
        """Carrega conjunto de obstáculos persistidos."""
        obstacles: Set[Tuple[int, int]] = set()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cell_x, cell_y FROM exploration_grid WHERE is_obstacle = 1")
                for row in cursor.fetchall():
                    obstacles.add((row["cell_x"], row["cell_y"]))
        except Exception as e:
            self.logger.debug(f"Aviso ao carregar obstáculos: {e}")
        return obstacles

    # -------------------------------------------------------------
    # Eventos de Stuck e Resultados de Ação
    # -------------------------------------------------------------
    def record_stuck_event(self, pos_x: float, pos_y: float, action: str) -> None:
        """Registra ponto onde o agente ficou travado para recuperação e aprendizado espacial."""
        try:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO stuck_events (timestamp, pos_x, pos_y, action_attempted, resolved)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (now, float(pos_x), float(pos_y), str(action)),
                )
                conn.commit()
        except Exception as e:
            self.logger.debug(f"Aviso ao registrar stuck event: {e}")

    def record_action_outcome(self, action_type: str, target: str, success: bool) -> None:
        """Registra resultado de execução de ação atômica."""
        try:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO action_outcomes (timestamp, action_type, target, success)
                    VALUES (?, ?, ?, ?)
                    """,
                    (now, str(action_type), str(target), 1 if success else 0),
                )
                conn.commit()
        except Exception as e:
            self.logger.debug(f"Aviso ao registrar ação: {e}")

    # -------------------------------------------------------------
    # Métricas da Sessão
    # -------------------------------------------------------------
    def update_session_metrics(
        self,
        steps_delta: int = 0,
        battles_won_delta: int = 0,
        battles_lost_delta: int = 0,
        heals_delta: int = 0,
    ) -> None:
        """Incrementa métricas da sessão atual."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE session_metadata
                    SET total_steps = total_steps + ?,
                        battles_won = battles_won + ?,
                        battles_lost = battles_lost + ?,
                        heals_completed = heals_completed + ?,
                        end_time = ?
                    WHERE session_id = ?
                    """,
                    (
                        steps_delta,
                        battles_won_delta,
                        battles_lost_delta,
                        heals_delta,
                        time.time(),
                        self._session_id,
                    ),
                )
                conn.commit()
        except Exception as e:
            self.logger.debug(f"Aviso ao atualizar métricas da sessão: {e}")

    def get_session_summary(self) -> Dict[str, Any]:
        """Retorna resumo estatístico da sessão ativa."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT session_id, start_time, end_time, total_steps, battles_won, battles_lost, heals_completed FROM session_metadata WHERE session_id = ?",
                    (self._session_id,),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            self.logger.debug(f"Aviso ao obter resumo da sessão: {e}")
        return {
            "session_id": self._session_id,
            "total_steps": 0,
            "battles_won": 0,
            "battles_lost": 0,
            "heals_completed": 0,
        }
