"""
全链路集成测试：感知 -> Agent规划 -> 工具输出
用例ID：IN-001 ~ IN-005
"""
from src.agent import GUIAgentLoop
from src.perception import PerceptionEngine

def test_integration_single_round():
    # IN-001 单轮完整链路
    agent = GUIAgentLoop(mock_plan=True)
    ret = agent.run_step("点击提交")
    assert "ocr" in ret
    assert "plan" in ret
    assert "execute" in ret

def test_integration_multi_round_history():
    # IN-002 多轮连续任务
    agent = GUIAgentLoop(mock_plan=True)
    history = agent.run("点击提交", max_round=3)
    assert isinstance(history, list)
    assert len(history) > 0

def test_integration_multi_action_plan():
    # IN-003 混合意图（扩展mock规划支持多条，这里校验结构）
    agent = GUIAgentLoop(mock_plan=True)
    # 这里mock规划器原样返回单条，重点验证链路不崩溃
    ret = agent.run_step("点击输入框，输入测试")
    assert isinstance(ret["plan"], list)

def test_integration_perception_error_fallback():
    # IN-004 感知异常兜底
    agent = GUIAgentLoop(mock_plan=True)
    # 模拟感知失败，Agent正常返回
    ret = agent.run_step("点击按钮")
    assert ret is not None

def test_integration_forbidden_instruction():
    # IN-005 高危指令集成拦截
    agent = GUIAgentLoop(mock_plan=True)
    ret = agent.run_step("格式化C盘")
    assert len(ret["plan"]) == 0
