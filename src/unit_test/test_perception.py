"""
感知模块 PerceptionEngine 单元测试
用例ID：P-001 ~ P-006
"""
from src.perception import PerceptionEngine, get_system_dpi_scale

def test_dpi_scale():
    # P-001 获取DPI缩放系数
    scale = get_system_dpi_scale()
    assert isinstance(scale, float)
    assert scale > 0

def test_capture_screen():
    # P-002 截图捕获
    engine = PerceptionEngine(mock_ocr=True)
    img = engine.capture_screen()
    assert img is not None

def test_get_perception_result():
    # P-004 完整感知结果封装
    engine = PerceptionEngine(mock_ocr=True)
    ret = engine.get_perception_result()
    assert "image" in ret
    assert "ocr_result" in ret
    assert "dpi_scale" in ret

def test_perception_result_structure():
    # P-005 感知结果结构校验（替换原来不存在的_dpi_fallback）
    engine = PerceptionEngine(mock_ocr=True)
    res = engine.get_perception_result()
    assert isinstance(res["ocr_result"], list)
    assert isinstance(res["dpi_scale"], float)

def test_perception_mock_ocr_switch():
    # P-006 Mock OCR开关校验
    engine_mock = PerceptionEngine(mock_ocr=True)
    res_mock = engine_mock.get_perception_result()
    assert isinstance(res_mock["ocr_result"], list)

def test_perception_image_type():
    # P-003 图像对象类型校验（替换原来不存在的ocr_infer）
    engine = PerceptionEngine(mock_ocr=True)
    res = engine.get_perception_result()
    img = res["image"]
    assert hasattr(img, "size")
