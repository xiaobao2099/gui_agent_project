"""
GUI智能体入口
第一阶段：桌面感知 + 动作执行 + Agent调度主循环
流程：用户指令 → 屏幕感知 → 任务规划 → 工具指令生成
说明：当前为Mock规划模式，仅输出结构化工具调用，不执行真实键鼠动作
"""
from src.agent import GUIAgentLoop

if __name__ == "__main__":
    print("===== 初始化GUI智能体 =====")
    agent = GUIAgentLoop(mock_plan=True)

    cmd_list = [
        "点击页面按钮",
        "按下回车",
        "输入测试文本"
    ]

    for user_cmd in cmd_list:
        print(f"\n======== 用户指令：{user_cmd} ========")
        result = agent.run_step(user_cmd)
        print(f"感知OCR结果：{result['ocr']['ocr_result']}")
        print(f"生成任务规划：{result['plan']}")
        print(f"工具执行返回：{result['execute']}")
