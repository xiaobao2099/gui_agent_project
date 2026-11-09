"""
桌面动作执行模块
1. 鼠标：点击、拖拽、滚轮
2. 键盘：输入文本、快捷键，剪贴板解决中文输入
3. DPI坐标转换：物理像素(截图/OCR输出) → 逻辑像素(pyautogui/pynput)
4. 高危动作拦截，安全fail‑safe保护
"""
import pyautogui
import pynput
from pynput.keyboard import Controller as KController
from pynput.mouse import Controller as MController, Button
import pyperclip
import platform
from typing import Dict

from src.perception.perception_engine import get_system_dpi_scale

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


class ActionExecutor:
    def __init__(self):
        self.mouse = MController()
        self.keyboard = KController()
        self.dpi_scale = get_system_dpi_scale()
        self._forbidden_keywords = ["delete", "rm", "format", "rmdir"]

    def physical_to_logical(self, px: int, py: int):
        """物理像素坐标(OCR输出) → 逻辑坐标(键鼠库使用)"""
        lx = int(px / self.dpi_scale)
        ly = int(py / self.dpi_scale)
        return lx, ly

    def click(self, physical_x: int, physical_y: int, button="left", clicks=1):
        """传入截图物理像素坐标，内部自动DPI转换后点击"""
        lx, ly = self.physical_to_logical(physical_x, physical_y)
        self.mouse.position = (lx, ly)
        btn = Button.left if button == "left" else Button.right
        for _ in range(clicks):
            self.mouse.click(btn)

    def drag(self, px_start, py_start, px_end, py_end):
        """拖拽：物理像素输入"""
        sx, sy = self.physical_to_logical(px_start, py_start)
        ex, ey = self.physical_to_logical(px_end, py_end)
        self.mouse.position = (sx, sy)
        self.mouse.press(Button.left)
        self.mouse.move(ex - sx, ey - sy)
        self.mouse.release(Button.left)

    def scroll(self, delta_y: int):
        """滚轮滚动，delta_y正数向上，负数向下"""
        self.mouse.scroll(0, delta_y)

    def type_text(self, text: str):
        """支持中文文本输入，使用剪贴板"""
        pyperclip.copy(text)
        if platform.system() == "Darwin":
            self.keyboard.press(pynput.keyboard.Key.cmd)
            self.keyboard.press("v")
            self.keyboard.release("v")
            self.keyboard.release(pynput.keyboard.Key.cmd)
        else:
            self.keyboard.press(pynput.keyboard.Key.ctrl)
            self.keyboard.press("v")
            self.keyboard.release("v")
            self.keyboard.release(pynput.keyboard.Key.ctrl)

    def hotkey(self, *keys):
        """快捷键，例如 hotkey('ctrl','c')"""
        pyautogui.hotkey(*keys)

    def execute_action(self, action_dict: Dict):
        act = action_dict.get("action")
        if act == "click":
            self.click(action_dict["x"], action_dict["y"])
        elif act == "drag":
            self.drag(action_dict["x1"], action_dict["y1"], action_dict["x2"], action_dict["y2"])
        elif act == "scroll":
            self.scroll(action_dict["dy"])
        elif act == "type":
            txt = action_dict["text"]
            for kw in self._forbidden_keywords:
                if kw in txt.lower():
                    raise RuntimeError(f"高危动作拦截，包含禁止关键词：{kw}")
            self.type_text(txt)
        elif act == "hotkey":
            self.hotkey(*action_dict["keys"])
        else:
            raise NotImplementedError(f"不支持动作 {act}")
