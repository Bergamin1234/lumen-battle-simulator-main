# src/ai/q_learning.py
import numpy as np
import random
from typing import Tuple

class QLearningAgent:
    def __init__(self, actions_count: int, alpha: float = 0.1, gamma: float = 0.95, epsilon: float = 0.2):
        self.q_table = {}
        self.actions_count = actions_count
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon

    def _get_state_key(self, hp_pct: float, enemy_hp_pct: float, energy: int) -> Tuple[int, int, int]:
        return (int(hp_pct * 10), int(enemy_hp_pct * 10), energy // 10)

    def choose_action(self, hp_pct: float, enemy_hp_pct: float, energy: int) -> int:
        state = self._get_state_key(hp_pct, enemy_hp_pct, energy)
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.actions_count)

        if random.random() < self.epsilon:
            return random.randint(0, self.actions_count - 1)
        return int(np.argmax(self.q_table[state]))

    def learn(self, state_tuple, action: int, reward: float, next_state_tuple):
        s = self._get_state_key(*state_tuple)
        s_next = self._get_state_key(*next_state_tuple)

        if s not in self.q_table:
            self.q_table[s] = np.zeros(self.actions_count)
        if s_next not in self.q_table:
            self.q_table[s_next] = np.zeros(self.actions_count)

        predict = self.q_table[s][action]
        target = reward + self.gamma * np.max(self.q_table[s_next])
        self.q_table[s][action] += self.alpha * (target - predict)