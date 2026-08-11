import os
import time
import cv2
import mss
import numpy as np


class VisionSystem:
    def __init__(self, templates_dir: str, confidence: float = 0.8, monitor_index: int = 1) -> None:
        self.templates_dir = templates_dir
        self.confidence = confidence
        self.monitor_index = monitor_index
        self.sct = mss.mss()
        self.templates: dict[str, np.ndarray] = {}
        self.load_templates()

    def load_templates(self) -> None:
        self.templates.clear()
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            return

        for filename in os.listdir(self.templates_dir):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                path = os.path.join(self.templates_dir, filename)
                img = cv2.imread(path, cv2.IMREAD_COLOR)
                if img is not None:
                    self.templates[filename] = img

    def get_screenshot(self) -> np.ndarray:
        monitor = self.sct.monitors[self.monitor_index]
        sct_img = self.sct.grab(monitor)
        frame = np.array(sct_img)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def find_template(
        self, 
        template_name: str, 
        screenshot: np.ndarray | None = None, 
        threshold: float | None = None
    ) -> tuple[int, int, int, int] | None:
        if threshold is None:
            threshold = self.confidence

        if template_name not in self.templates:
            return None

        template = self.templates[template_name]
        if screenshot is None:
            screenshot = self.get_screenshot()

        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = template.shape[:2]
            return (max_loc[0], max_loc[1], w, h)
        return None

    def template_exists(self, template_name: str, threshold: float | None = None) -> bool:
        return self.find_template(template_name, threshold=threshold) is not None

    def wait_template(
        self, 
        template_name: str, 
        timeout: float = 10.0, 
        check_interval: float = 0.2
    ) -> tuple[int, int, int, int] | None:
        start_time = time.time()
        while time.time() - start_time < timeout:
            location = self.find_template(template_name)
            if location:
                return location
            time.sleep(check_interval)
        return None

    def get_center_coords(self, match_box: tuple[int, int, int, int]) -> tuple[int, int]:
        x, y, w, h = match_box
        return (x + w // 2, y + h // 2)