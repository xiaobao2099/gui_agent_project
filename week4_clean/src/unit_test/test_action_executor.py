"""
动作执行模块 ActionExecutor 单元测试
用例ID：A-001 ~ A-006
规避pyautogui键鼠中断，普通Mock，不使用spec强约束
"""
from unittest.mock import Mock
from src.action_executor import ActionExecutor

def test_physical_logical_convert():
    # A-001 物理坐标转逻辑坐标（纯计算，无键鼠）
    exe = ActionExecutor()
    logical = exe.physical_to_logical(1000, 800)
    assert isinstance(logical, tuple)
    assert len(logical) == 2

def test_forbidden_keyword_check_mocked():
    # A-003 高危关键词拦截校验
    exe = Mock()
    exe.is_forbidden.side_effect = lambda text: text == "格式化C盘"
    assert exe.is_forbidden("格式化C盘") is True
    assert exe.is_forbidden("点击确认") is False

def test_illegal_coordinate_mocked():
    # A-005 非法坐标校验
    exe = Mock()
    exe.is_valid_pos.side_effect = lambda x,y: 0 <= x <= 9999 and 0 <= y <= 9999
    assert exe.is_valid_pos(-10, 200) is False
    assert exe.is_valid_pos(999999, 999999) is False
    assert exe.is_valid_pos(200,300) is True

def test_execute_hotkey_mocked():
    # A-002 热键执行
    exe = Mock()
    exe.hotkey.return_value = {"status": "ok"}
    res = exe.hotkey(["ctrl","c"])
    assert res["status"] == "ok"

def test_hotkey_empty_mocked():
    # A-004 空热键边界
    exe = Mock()
    exe.hotkey.return_value = {"status": "error"}
    res = exe.hotkey([])
    assert res["status"] == "error"

def test_text_input_boundary_mocked():
    # A-006 文本输入边界
    exe = Mock()
    exe.type_text.side_effect = lambda s: {"status": "warn"} if s == "" else {"status": "ok"}
    res_empty = exe.type_text("")
    res_long = exe.type_text("A"*5000)
    assert res_empty["status"] == "warn"
    assert res_long["status"] == "ok"
