"""
LUMENA BOT v3.6.1 — REAL-WORLD PHYSICAL BATTLE EXECUTION PROOF
==============================================================
Script de execução física no desktop real (Windows + Chrome + Lumena.gg).
Valida a cadeia completa:
PERCEPTION -> DECISION -> INPUT REQUEST -> INPUT DISPATCH -> GAME RESPONSE -> VISUAL VERIFICATION -> RESULT.JSON

ZERO FAKE PASS:
- Não gera resultados sintéticos
- Exige janela real do Google Chrome / Lumena.gg
- Gera pacote de evidências em debug/evidence/<timestamp>/
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional
import numpy as np
import cv2

# Configura path raiz do projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config.settings import BotConfig, CRITICAL_HP_RATIO, HEALING_HP_RATIO
from src.core.event_bus import EventBus, EventType, BotEvent
from src.input.target_window import TargetWindowManager, TargetWindowInfo
from src.input.input_controller import InputController
from src.perception.screen_capture import ScreenCapture
from src.perception.state_classifier import StateClassifier
from src.perception.combat_vision import CombatVisionAnalyzer
from src.combat.decision_engine import CombatDecisionEngine
from src.combat.combat_agent import CombatAgent
from src.combat.skill_executor import SkillExecutor

# Configura logging para stdout e arquivo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("LumenaRealBattleV361")


def run_real_battle_execution_proof() -> Dict[str, Any]:
    print("=" * 70)
    print("   LUMENA BOT v3.6.1 — REAL-WORLD PHYSICAL BATTLE EXECUTION PROOF")
    print("   ZERO FAKE PASS — REAL WIN32 INPUT & REAL VISUAL VERIFICATION")
    print("=" * 70)

    ts_str = time.strftime("%Y%m%d_%H%M%S")
    evidence_dir = os.path.abspath(os.path.join("debug", "evidence", f"battle_proof_{ts_str}"))
    os.makedirs(evidence_dir, exist_ok=True)

    event_bus = EventBus()
    event_bus.clear_history()

    captured_events = []
    def on_event(event: BotEvent):
        captured_events.append({
            "timestamp": event.timestamp,
            "type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            "category": event.category,
            "level": event.level,
            "message": event.message,
            "data": event.data,
        })

    for et in EventType:
        event_bus.subscribe(et, on_event)

    # 1. Inicializa subsistemas reais
    input_ctrl = InputController(preferred_backend="win32")
    screen_cap = ScreenCapture()
    state_classifier = StateClassifier()
    combat_vision = CombatVisionAnalyzer()
    decision_engine = CombatDecisionEngine()
    skill_executor = SkillExecutor(input_controller=input_ctrl, event_bus=event_bus)
    combat_agent = CombatAgent(decision_engine=decision_engine, skill_executor=skill_executor)

    # 2. Descobre e seleciona janela alvo real (Chrome / Lumena.gg)
    print("\n[ETAPA 1/7] Descoberta e Verificação de Janela Alvo...")
    win_mgr = input_ctrl.window_manager
    candidates = win_mgr.discover_candidates(filter_browsers=True)
    target = win_mgr.get_active_target() or win_mgr.find_target_window()

    window_data = {
        "target_found": target is not None,
        "hwnd": target.hwnd if target else 0,
        "pid": getattr(target, "pid", 0) if target else 0,
        "process_name": target.process_name if target else "NONE",
        "title": target.title if target else "NONE",
        "is_foreground": False,
        "canvas_focused": False,
        "total_candidates": len(candidates),
    }

    if not target:
        print("⚠️ [AVISO] Nenhuma janela de navegador Chrome/Lumena.gg foi encontrada em execução.")
        print("   Para validar em tempo real, abra https://lumena.gg no Google Chrome.")
        
        result_json = {
            "battle_detected": False,
            "enemy_detected": False,
            "player_detected": False,
            "crystal_search_blocked": False,
            "skills_detected": 0,
            "skills_available": 0,
            "decision_made": False,
            "input_requested": False,
            "input_dispatched": False,
            "action_verified": False,
            "visual_delta": 0.0,
            "physically_validated": False,
            "status": "NO_TARGET_WINDOW",
        }

        with open(os.path.join(evidence_dir, "window.json"), "w", encoding="utf-8") as f:
            json.dump(window_data, f, indent=2, ensure_ascii=False)
        with open(os.path.join(evidence_dir, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)
        with open(os.path.join(evidence_dir, "events.json"), "w", encoding="utf-8") as f:
            json.dump(captured_events, f, indent=2, ensure_ascii=False)

        print(f"📁 Pacote de evidências salvo em: {evidence_dir}")
        return result_json

    # Foca a janela do jogo e o canvas
    is_fg = input_ctrl.focus_game_window()
    canvas_focused = win_mgr.ensure_canvas_focus(0.5, 0.5)
    window_data["is_foreground"] = is_fg
    window_data["canvas_focused"] = canvas_focused
    print(f"✓ Janela Alvo: '{target.title}' (HWND: {target.hwnd}, PID: {target.pid})")
    print(f"✓ Foco Confirmado: {is_fg} | Canvas WebGL: {canvas_focused}")

    # 3. Captura frame_before real
    print("\n[ETAPA 2/7] Captura de Frame Pré-Ação (frame_before)...")
    time.sleep(0.3)
    frame_before, ts_before = screen_cap.capture_frame()
    if frame_before is None or frame_before.size == 0:
        print("❌ [ERRO] Falha ao capturar frame da tela.")
        frame_before = np.zeros((720, 1280, 3), dtype=np.uint8)

    cv2.imwrite(os.path.join(evidence_dir, "before.png"), frame_before)

    # 4. Análise de Percepção Real (Player, Enemy, Skills, Battle State)
    print("\n[ETAPA 3/7] Análise de Percepção Visual (Perception)...")
    snapshot = state_classifier.classify_frame(frame_before, timestamp=ts_before)
    csnap = combat_vision.analyze_frame(frame_before, timestamp=ts_before)

    perception_data = {
        "battle_detected": csnap.in_battle,
        "player_detected": csnap.player_detected,
        "player_bbox": list(csnap.player_bbox),
        "player_center": list(csnap.player_center),
        "player_hp": csnap.player_hp,
        "enemy_detected": csnap.target_enemy is not None,
        "enemy_bbox": list(csnap.enemy_bbox) if csnap.target_enemy else [0, 0, 0, 0],
        "enemy_center": list(csnap.enemy_center) if csnap.target_enemy else [0, 0],
        "confidence": csnap.confidence,
        "distance": csnap.distance,
        "skills_detected": len(csnap.available_skills),
        "skills": [
            {
                "index": s.slot_index,
                "name": s.skill_name,
                "center": (s.center_x, s.center_y),
                "hotkey": s.hotkey,
                "element": s.element.name if s.element else "NORMAL",
                "range": s.range,
                "available": s.available,
                "cooldown": s.cooldown,
                "confidence": s.confidence,
            }
            for s in csnap.available_skills
        ],
    }

    print(f"✓ Batalha Detectada: {csnap.in_battle}")
    print(f"✓ Inimigo Detectado: {csnap.target_enemy is not None} ({csnap.target_enemy.name if csnap.target_enemy else 'Nenhum'})")
    print(f"✓ Jogador Detectado: {csnap.player_detected} | HP: {csnap.player_hp*100:.1f}%")
    print(f"✓ Slots de Habilidades Detectados: {len(csnap.available_skills)}")

    # Gera frame anotado com caixas semânticas
    annotated = frame_before.copy()
    if csnap.player_detected and csnap.player_bbox != (0, 0, 0, 0):
        px, py, pw, ph = csnap.player_bbox
        cv2.rectangle(annotated, (px, py), (px + pw, py + ph), (0, 255, 0), 2)
        cv2.putText(annotated, "[PLAYER]", (px, max(15, py - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    if csnap.target_enemy:
        ex, ey, ew, eh = csnap.enemy_bbox
        cv2.rectangle(annotated, (ex, ey), (ex + ew, ey + eh), (0, 0, 255), 2)
        cv2.putText(annotated, f"[ENEMY: {csnap.target_enemy.name}]", (ex, max(15, ey - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    for s in csnap.available_skills:
        cv2.rectangle(annotated, (s.screen_x, s.screen_y), (s.screen_x + s.width, s.screen_y + s.height), (255, 200, 0), 2)
        cv2.putText(annotated, f"#{s.slot_index} {s.skill_name or ''}", (s.screen_x, max(15, s.screen_y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 200, 0), 1)

    cv2.imwrite(os.path.join(evidence_dir, "annotated.png"), annotated)

    # 5. Tomada de Decisão (Decision)
    print("\n[ETAPA 4/7] Tomada de Decisão de Combate (Decision)...")
    decision = decision_engine.evaluate_combat_snapshot(csnap)

    decision_data = {
        "decision_made": True,
        "action_type": decision.action_type,
        "selected_skill": decision.selected_skill.skill_name if decision.selected_skill else None,
        "selected_slot": decision.selected_skill.slot_index if decision.selected_skill else None,
        "hotkey": decision.hotkey,
        "score": decision.score,
        "reason": decision.reason,
    }
    print(f"✓ Decisão: {decision.action_type} | Habilidade: {decision_data['selected_skill']} | Hotkey: '{decision.hotkey}'")
    print(f"✓ Razão: {decision.reason}")

    # 6. Despacho Físico de Entrada (Input Dispatch)
    print("\n[ETAPA 5/7] Despacho Físico de Entrada (Input Dispatch)...")
    input_requested = decision.action_type in ("USE_SKILL", "OPEN_FIGHT_MENU", "APPROACH_TARGET")
    input_dispatched = False
    input_latency = 0.0

    if decision.action_type == "USE_SKILL" and decision.selected_skill:
        input_dispatched, input_latency = skill_executor.execute_skill(decision.selected_skill, frame_before=frame_before)
    elif decision.action_type == "OPEN_FIGHT_MENU" and csnap.fight_button_pos:
        input_dispatched = input_ctrl.click(csnap.fight_button_pos[0], csnap.fight_button_pos[1])
    elif decision.action_type == "APPROACH_TARGET" and decision.move_direction:
        input_dispatched = input_ctrl.press_key(decision.move_direction, duration=0.15)

    input_data = {
        "input_requested": input_requested,
        "input_dispatched": input_dispatched,
        "input_type": "HOTKEY" if decision.hotkey else "CLICK",
        "key": decision.hotkey,
        "target_hwnd": target.hwnd,
        "target_pid": target.pid,
        "latency": input_latency,
    }
    print(f"✓ Input Solicitado: {input_requested} | Input Despachado: {input_dispatched} ({input_latency*1000:.1f}ms)")

    # 7. Verificação Pós-Ação (Closed-Loop Action Verification)
    print("\n[ETAPA 6/7] Captura Pós-Ação e Verificação em Malha Fechada...")
    time.sleep(0.3)
    frame_after, ts_after = screen_cap.capture_frame()
    if frame_after is None or frame_after.size == 0:
        frame_after = frame_before.copy()

    cv2.imwrite(os.path.join(evidence_dir, "after.png"), frame_after)

    # Calcula diferença de pixels
    diff_frame = np.abs(frame_before.astype(np.float32) - frame_after.astype(np.float32)).astype(np.uint8)
    cv2.imwrite(os.path.join(evidence_dir, "diff.png"), diff_frame)

    confirmed, visual_delta = input_ctrl.compute_visual_delta(frame_before, frame_after)
    action_verified = bool(input_dispatched and (confirmed or visual_delta > 0.005))

    print(f"✓ Variação Visual (Delta): {visual_delta:.4f} (Limiar: > 0.0050)")
    print(f"✓ Ação Verificada: {'VERIFIED (PASS)' if action_verified else 'UNCONFIRMED'}")

    # 8. Consolidação do Resultado Final
    print("\n[ETAPA 7/7] Consolidação do Pacote de Evidências (result.json)...")
    crystal_search_blocked = bool(csnap.in_battle and csnap.target_enemy and csnap.player_hp > CRITICAL_HP_RATIO)
    skills_available_count = sum(1 for s in csnap.available_skills if s.available and s.cooldown <= 0)

    physically_validated = bool(
        target is not None and
        csnap.in_battle and
        csnap.target_enemy is not None and
        input_dispatched and
        action_verified
    )

    result_json = {
        "battle_detected": bool(csnap.in_battle),
        "enemy_detected": bool(csnap.target_enemy is not None),
        "player_detected": bool(csnap.player_detected),
        "crystal_search_blocked": crystal_search_blocked,
        "skills_detected": len(csnap.available_skills),
        "skills_available": skills_available_count,
        "decision_made": True,
        "input_requested": input_requested,
        "input_dispatched": input_dispatched,
        "action_verified": action_verified,
        "visual_delta": visual_delta,
        "physically_validated": physically_validated,
    }

    # Salva todos os arquivos JSON
    with open(os.path.join(evidence_dir, "window.json"), "w", encoding="utf-8") as f:
        json.dump(window_data, f, indent=2, ensure_ascii=False)
    with open(os.path.join(evidence_dir, "perception.json"), "w", encoding="utf-8") as f:
        json.dump(perception_data, f, indent=2, ensure_ascii=False)
    with open(os.path.join(evidence_dir, "decision.json"), "w", encoding="utf-8") as f:
        json.dump(decision_data, f, indent=2, ensure_ascii=False)
    with open(os.path.join(evidence_dir, "input.json"), "w", encoding="utf-8") as f:
        json.dump(input_data, f, indent=2, ensure_ascii=False)
    with open(os.path.join(evidence_dir, "events.json"), "w", encoding="utf-8") as f:
        json.dump(captured_events, f, indent=2, ensure_ascii=False)
    with open(os.path.join(evidence_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result_json, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("   RELATÓRIO DE EXECUÇÃO REAL — LUMENA BOT v3.6.1")
    print("=" * 70)
    print(json.dumps(result_json, indent=2))
    print(f"\n📁 Pacote completo de evidências salvo em:\n{evidence_dir}")

    return result_json


if __name__ == "__main__":
    run_real_battle_execution_proof()
