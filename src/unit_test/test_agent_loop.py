"""
Agent调度模块 GUIAgentLoop 单元测试
用例ID：AG-001 ~ AG-007
"""
from src.agent import GUIAgentLoop

def test_agent_init():
    # AG-001
    agent = GUIAgentLoop(mock_plan=True)
    assert agent is not None
    assert agent.mock_plan is True

def test_agent_run_step_click():
    # AG-002
    agent = GUIAgentLoop(mock_plan=True)
    res = agent.run_step("点击页面按钮")
    assert res["user_instruction"] == "点击页面按钮"
    assert len(res["plan"]) == 1
    assert res["plan"][0]["tool"] == "action_click"

def test_agent_run_step_enter():
    # AG-003
    agent = GUIAgentLoop(mock_plan=True)
    res = agent.run_step("按下回车")
    assert res["plan"][0]["tool"] == "action_hotkey"

def test_agent_run_step_empty():
    # AG-004
    agent = GUIAgentLoop(mock_plan=True)
    res = agent.run_step("无有效指令")
    assert len(res["plan"]) == 0

def test_agent_multi_round_run():
    # AG-005
    agent = GUIAgentLoop(mock_plan=True)
    history = agent.run("点击页面按钮", max_round=2)
    assert len(history) >= 1

def test_agent_empty_instruction():
    # AG-006 空指令边界
    agent = GUIAgentLoop(mock_plan=True)
    res = agent.run_step("")
    assert len(res["plan"]) == 0

def test_agent_special_char_instruction():
    # AG-007 特殊字符鲁棒
    agent = GUIAgentLoop(mock_plan=True)
    res = agent.run_step("点击【确定】按钮!!!@@@")
    assert len(res["plan"]) == 1
