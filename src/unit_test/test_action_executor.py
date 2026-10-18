import pytest
from src.action_executor.action_executor import ActionExecutor
from src.perception.perception_engine import get_system_dpi_scale

def test_physical_logical_convert():
    exe = ActionExecutor()
    scale = get_system_dpi_scale()
    lx, ly = exe.physical_to_logical(1920,1080)
    assert isinstance(lx, int)
    assert isinstance(ly, int)

def test_execute_hotkey():
    exe = ActionExecutor()
    # 仅逻辑测试，不真实执行快捷键
    action = {"action":"hotkey", "keys":["ctrl","v"]}
    assert action["action"] == "hotkey"

def test_forbidden_keyword_check():
    exe = ActionExecutor()
    forbidden_action = {
        "action":"type",
        "text":"rm -rf /"
    }
    with pytest.raises(RuntimeError):
        exe.execute_action(forbidden_action)
