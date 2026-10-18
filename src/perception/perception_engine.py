"""
桌面屏幕感知模块（EasyOCR版本，兼容Python3.14，支持测试mock模式，避免单元测试下载模型）
功能：跨平台截图、离线OCR识别、OCR噪声过滤、DPI缩放因子获取、UI框绘制
全部本地运行，无公有云调用
"""
import os
import sys
import platform
import mss
from mss import MSS
import numpy as np
from PIL import Image, ImageDraw
from typing import List, Dict


def get_system_dpi_scale() -> float:
    """
    获取系统DPI缩放因子（物理像素 / 逻辑像素）
    """
    scale = 1.0
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            hdc = ctypes.windll.user32.GetDC(0)
            phys_w = ctypes.windll.gdi32.GetDeviceCaps(hdc, 118)
            log_w = ctypes.windll.gdi32.GetDeviceCaps(hdc, 8)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            if log_w > 0:
                scale = phys_w / log_w
        except Exception:
            scale = 1.0
    elif platform.system() == "Darwin":
        scale = 2.0
    return round(scale, 2)


class PerceptionEngine:
    def __init__(self, confidence_thresh: float = 0.6, mock_ocr: bool = False):
        """
        :param confidence_thresh: OCR置信度阈值
        :param mock_ocr: True=单元测试mock模式，不加载easyocr、不联网下载模型
        """
        self.confidence_thresh = confidence_thresh
        self.sct = MSS()
        self.dpi_scale = get_system_dpi_scale()
        self.mock_ocr = mock_ocr
        self.reader = None

        if not self.mock_ocr:
            # 仅非测试模式才加载EasyOCR，会下载离线模型
            import easyocr
            self.reader = easyocr.Reader(['ch_sim','en'], gpu=False)

    def capture_screen(self, monitor_idx: int = 1) -> Image.Image:
        """捕获屏幕，返回PIL RGB图像（物理像素）"""
        monitor = self.sct.monitors[monitor_idx]
        shot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return img

    def run_ocr(self, pil_img: Image.Image) -> List[Dict]:
        """OCR识别，mock模式直接返回空列表，真实模式调用easyocr"""
        if self.mock_ocr or self.reader is None:
            return []
        img_np = np.array(pil_img)
        raw_result = self.reader.readtext(img_np)
        output = []
        for item in raw_result:
            bbox, text, conf = item
            if conf < self.confidence_thresh:
                continue
            x1, y1 = int(bbox[0][0]), int(bbox[0][1])
            x2, y2 = int(bbox[2][0]), int(bbox[2][1])
            w = x2 - x1
            h = y2 - y1
            if w < 8 or h <8:
                continue
            output.append({
                "text": text,
                "bbox": [x1,y1,x2,y2],
                "conf": float(conf)
            })
        return output

    def draw_ocr_bbox(self, pil_img: Image.Image, ocr_list: List[Dict], save_path: str):
        draw = ImageDraw.Draw(pil_img)
        for item in ocr_list:
            x1,y1,x2,y2 = item["bbox"]
            draw.rectangle([x1,y1,x2,y2], outline="red", width=2)
        pil_img.save(save_path)

    def get_perception_result(self, monitor_idx:int=1) -> Dict:
        img = self.capture_screen(monitor_idx)
        ocr_res = self.run_ocr(img)
        return {
            "image": img,
            "ocr_result": ocr_res,
            "dpi_scale": self.dpi_scale
        }
