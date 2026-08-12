import os
import unittest
import tempfile
import shutil

from src.models.enums import AgentState, MoveDirection, Element
from src.models.lumen import StateSnapshot, BattleTelemetry, AtomicAction
from src.memory.world_memory import WorldMemory
from src.memory.experience_store import ExperienceStore
from src.memory.memory_manager import MemoryManager


class TestMemoryLayer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_experience.db")
        self.world_memory = WorldMemory(grid_cell_size=1.0, max_snapshots=10, max_actions=20)
        self.store = ExperienceStore(db_path=self.db_path)
        self.manager = MemoryManager(world_memory=self.world_memory, experience_store=self.store)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)


    # 1. Criação do WorldMemory
    def test_world_memory_initialization(self):
        wm = WorldMemory()
        self.assertEqual(wm.estimated_position, (0.0, 0.0))
        self.assertEqual(wm.consecutive_failures, 0)
        self.assertEqual(wm.consecutive_successes, 0)
        self.assertEqual(len(wm.exploration_heatmap), 0)
        self.assertEqual(len(wm.obstacle_map), 0)

    # 2. Atualização de Posição
    def test_position_update(self):
        wm = WorldMemory()
        wm.set_position(10.0, 5.0)
        self.assertEqual(wm.estimated_position, (10.0, 5.0))

        new_pos = wm.update_position(2.0, -1.0, scale=1.0)
        self.assertEqual(new_pos, (12.0, 4.0))
        self.assertEqual(wm.estimated_position, (12.0, 4.0))

    # 3. Atualização do Heading
    def test_heading_update(self):
        wm = WorldMemory()
        wm.set_heading_from_direction("w")
        self.assertEqual(wm.heading_vector, (0.0, -1.0))

        wm.set_heading_from_direction("d")
        self.assertEqual(wm.heading_vector, (1.0, 0.0))

    # 4. Heatmap de Exploração
    def test_exploration_heatmap(self):
        wm = WorldMemory(grid_cell_size=1.0)
        wm.set_position(2.3, 3.8)
        cell = wm.record_visit()
        self.assertEqual(cell, (2, 3))
        self.assertEqual(wm.get_visit_cost(2, 3), 1)

        wm.record_visit(2.1, 3.4)
        self.assertEqual(wm.get_visit_cost(2, 3), 2)

        # Vizinho menos visitado
        best_neighbor = wm.get_least_visited_neighbor(2, 3)
        self.assertIn(best_neighbor, [(2, 2), (3, 3), (2, 4), (1, 3)])
        self.assertEqual(wm.get_visit_cost(best_neighbor[0], best_neighbor[1]), 0)

    # 5. Registro de Obstáculos
    def test_obstacle_registration(self):
        wm = WorldMemory()
        wm.register_obstacle(5, 5)
        self.assertTrue(wm.is_obstacle(5, 5))
        self.assertFalse(wm.is_obstacle(5, 6))

        wm.clear_obstacle(5, 5)
        self.assertFalse(wm.is_obstacle(5, 5))

    # 6. Registro e Recalibração por Landmark
    def test_landmarks_and_recalibration(self):
        wm = WorldMemory()
        wm.set_position(100.0, 100.0)
        wm.register_landmark("blue_crystal", rel_pos=(50, -20), confidence=0.9)

        lm = wm.get_landmark("blue_crystal")
        self.assertIsNotNone(lm)
        self.assertEqual(lm["name"], "blue_crystal")
        self.assertEqual(lm["confidence"], 0.9)

        # Recalibração de drift com âncora fixa
        recalibrated = wm.recalibrate_position_from_landmark(
            "blue_crystal",
            known_anchor_pos=(100.5, 99.8),
            current_rel_pos=(50, -20),
        )
        self.assertTrue(recalibrated)
        self.assertEqual(wm.estimated_position, (100.0, 100.0))

    # 7 & 8. Contadores de Falhas e Sucessos (Watchdog)
    def test_watchdog_success_and_failure(self):
        wm = WorldMemory()
        wm.record_failure()
        wm.record_failure()
        self.assertEqual(wm.consecutive_failures, 2)
        self.assertEqual(wm.consecutive_successes, 0)

        wm.record_success()
        self.assertEqual(wm.consecutive_failures, 0)
        self.assertEqual(wm.consecutive_successes, 1)

        wm.reset_watchdog()
        self.assertEqual(wm.consecutive_failures, 0)
        self.assertEqual(wm.consecutive_successes, 0)

    # 9 & 16. Bounded Buffers e Ausência de Vazamento de Memória
    def test_bounded_buffers_no_memory_leak(self):
        wm = WorldMemory(max_snapshots=10, max_actions=20)

        # Adiciona 50 snapshots
        for i in range(50):
            snap = StateSnapshot(
                timestamp=float(i),
                screen_state=AgentState.EXPLORING,
            )
            wm.add_snapshot(snap)

        self.assertEqual(len(wm.recent_snapshots), 10)
        self.assertEqual(wm.recent_snapshots[-1].timestamp, 49.0)

        # Adiciona 50 ações
        for i in range(50):
            act = AtomicAction(action_type="KEY_PRESS", target="w")
            wm.add_action(act, success=True)

        self.assertEqual(len(wm.recent_actions), 20)

    # 10, 11 & 12. MemoryManager, Persistência e Recuperação
    def test_memory_manager_persistence_and_restore(self):
        # Ingestão de estado com Cristal
        snap = StateSnapshot(
            timestamp=100.0,
            screen_state=AgentState.SEARCHING_CRYSTAL,
            crystal_detected=True,
            crystal_relative_pos=(20, 10),
        )
        self.manager.ingest_snapshot(snap)

        # Verifica persistência no SQLite
        persisted_landmarks = self.store.load_landmarks()
        self.assertEqual(len(persisted_landmarks), 1)
        self.assertEqual(persisted_landmarks[0]["name"], "blue_crystal")

        # Registra passos com sucesso
        action = AtomicAction(action_type="KEY_PRESS", target="d", duration=0.15)
        self.manager.record_action_result(action, verified_success=True)

        summary = self.manager.get_world_summary()
        self.assertGreater(summary["estimated_position"][0], 0.0)
        self.assertEqual(summary["session_metrics"]["total_steps"], 1)

        # Cria nova instância e restaura da persistência
        new_wm = WorldMemory()
        new_manager = MemoryManager(world_memory=new_wm, experience_store=self.store)
        new_manager.restore_from_disk()

        self.assertIn("blue_crystal", new_wm.known_landmarks)

    # 13. Tratamento de Banco/Arquivo Inexistente ou em Memória
    def test_experience_store_in_memory_and_fault_tolerance(self):
        in_memory_store = ExperienceStore(db_path=":memory:")
        in_memory_store.save_landmark("test_portal", 5.0, 10.0, 0.8)
        lms = in_memory_store.load_landmarks()
        self.assertEqual(len(lms), 1)
        self.assertEqual(lms[0]["name"], "test_portal")

    # 14 & 15. Tolerância a Dados Inválidos e Integração StateSnapshot
    def test_state_snapshot_integration_and_invalid_data_tolerance(self):
        # Ingestão de None
        self.manager.ingest_snapshot(None)
        self.manager.record_action_result(None, verified_success=False)

        # Ingestão de batalha com vitória
        telemetry = BattleTelemetry(in_battle=True, victory_detected=True)
        battle_snap = StateSnapshot(
            timestamp=200.0,
            screen_state=AgentState.BATTLE_RESULT,
            battle_telemetry=telemetry,
        )
        self.manager.ingest_snapshot(battle_snap)

        summary = self.manager.get_world_summary()
        self.assertEqual(summary["session_metrics"]["battles_won"], 1)

        # Detecção de Stuck após 3 falhas consecutivas
        action_walk = AtomicAction(action_type="KEY_PRESS", target="w")
        self.manager.record_action_result(action_walk, verified_success=False)
        self.manager.record_action_result(action_walk, verified_success=False)
        self.manager.record_action_result(action_walk, verified_success=False)

        self.assertTrue(self.manager.is_stuck())
        updated_summary = self.manager.get_world_summary()
        self.assertGreater(updated_summary["total_obstacles"], 0)


if __name__ == "__main__":
    unittest.main()

