from src.perception.perception_engine import PerceptionEngine
from src.action_executor.action_executor import ActionExecutor

if __name__ == "__main__":
    # 真实运行：mock_ocr=False，加载EasyOCR离线OCR
    pe = PerceptionEngine(mock_ocr=False)
    perception_result = pe.get_perception_result()
    print("DPI缩放：", perception_result["dpi_scale"])
    print("OCR识别结果：", perception_result["ocr_result"])

    executor = ActionExecutor()
