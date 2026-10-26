"""
GUI智能体 Agent 主循环调度模块 GUIAgentLoop
功能：
1. 接收用户自然语言指令 + 感知模块多模态输入（截图+OCR）
2. 简单任务规划（Mock规划器，下一阶段替换为LLM）
3. 工具路由：调用感知模块、动作执行模块
4. 执行循环、结果回传、终止判断
依赖：perception.PerceptionEngine、action_executor.ActionExecutor
"""
from src.perception import PerceptionEngine, get_system_dpi_scale


class GUIAgentLoop:
    def __init__(self, mock_plan: bool = True):
        self.perception = PerceptionEngine(mock_ocr=True)
        self.mock_plan = mock_plan
        # 测试模式：不实例化真实ActionExecutor，避免执行键鼠
        # 工具定义，返回结构化指令，不直接调用真实动作函数
        self.tool_map = {
            "action_click": lambda p: {"status": "ok", "tool": "action_click", "param": p},
            "action_hotkey": lambda p: {"status": "ok", "tool": "action_hotkey", "param": p},
            "action_type": lambda p: {"status": "ok", "tool": "action_type", "param": p}
        }

    def _plan(self, user_instruction: str, ocr_result: list):
        """
        Mock任务规划器：下一阶段替换为DeepSeek Coder LLM输出
        返回规划列表 [{"tool": "xxx", "args": {...}}]
        """
        if not self.mock_plan:
            raise NotImplementedError("LLM planner not implemented in stage1")

        instruction = user_instruction.lower()
        if "点击" in instruction:
            return [{"tool": "action_click", "args": {"pos": (300, 200)}}]
        elif "回车" in instruction or "enter" in instruction:
            return [{"tool": "action_hotkey", "args": {"key": "enter"}}]
        elif "输入" in instruction:
            return [{"tool": "action_type", "args": {"text": "mock_input_text"}}]
        else:
            return []

    def run_step(self, user_instruction: str):
        """单步Agent执行：感知 -> 规划 -> 工具调用"""
        # 1. 感知：截图+OCR
        ocr_result = self.perception.get_perception_result()
        # 2. 任务规划
        plan = self._plan(user_instruction, ocr_result)
        execute_result = []
        # 3. 依次调用工具（mock调用，不碰真实键鼠）
        for step in plan:
            tool_name = step["tool"]
            args = step["args"]
            if tool_name in self.tool_map:
                ret = self.tool_map[tool_name](args)
                execute_result.append({"tool": tool_name, "args": args, "ret": ret})
        return {
            "user_instruction": user_instruction,
            "ocr": ocr_result,
            "plan": plan,
            "execute": execute_result
        }

    def run(self, user_instruction: str, max_round: int = 3):
        """多轮主循环（最多max_round轮）"""
        history = []
        for r in range(max_round):
            res = self.run_step(user_instruction)
            history.append(res)
            if len(res["plan"]) == 0:
                break
        return history
