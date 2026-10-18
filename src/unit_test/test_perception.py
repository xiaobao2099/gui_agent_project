import pytest
from src.perception.perception_engine import PerceptionEngine, get_system_dpi_scale

def test_dpi_scale():
    scale = get_system_dpi_scale()
    assert isinstance(scale, float)
    assert scale > 0

def test_capture_screen():
    pe = PerceptionEngine(mock_ocr=True)
    img = pe.capture_screen()
    assert img is not None
    assert img.mode == "RGB"

def test_ocr_infer():
    pe = PerceptionEngine(mock_ocr=True)
    img = pe.capture_screen()
    res = pe.run_ocr(img)
    assert isinstance(res, list)

def test_get_perception_result():
    pe = PerceptionEngine(mock_ocr=True)
    ret = pe.get_perception_result()
    assert "image" in ret
    assert "ocr_result" in ret
    assert "dpi_scale" in ret
