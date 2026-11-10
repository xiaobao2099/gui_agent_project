# 中小企业私有化桌面 GUI 智能体

基于 Qwen2.5-VL-7B-Instruct + QLoRA 微调的桌面 GUI 自动化系统。客户端运行在 Win11 员工机上，只负责截图与执行动作；推理服务部署在企业内网 GPU 服务器，模型权重与业务截图不出内网。

## 核心结果

| 指标 | 结果 |
| --- | --- |
| 单元测试 | 24 条全通过 |
| 验收用例 | 20 条全通过（含 Windows 真机复跑） |
| 可训练参数 | 5,046,272 / 8,297,212,928 = 0.0608% |
| 视觉线训练显存峰值 | 10.96 GB（4bit 量化，RTX 3090 可跑） |
| 动作生效判定 | 截图差阈值 1.2，由真实样本反推 |

## 目录结构

```
├── client_v2.0.py           Win11 瘦客户端（截图 / 请求 / 执行 / 失败重试）
├── main.py                  感知-规划-执行主循环入口（mock 规划模式）
├── src/
│   ├── perception/          屏幕感知、DPI 换算、OCR 过滤
│   ├── action_executor/     动作白名单、坐标校验、键鼠执行
│   ├── agent/               意图规划与多轮调度
│   └── unit_test/           24 条单元测试
├── server/
│   ├── infer_server.py      内网推理服务（FastAPI）
│   └── compare_base_vs_lora.py  基座与 LoRA 输出对比
├── data/
│   ├── finetune/            QLoRA 训练脚本
│   └── realdata/            真实桌面截图四张 + 标注
├── tests/acceptance_20cases.py  20 条验收用例
├── docs/
│   ├── reports/             六份文档（见下）
│   └── 演示视频录制脚本.md
├── test_artifacts/          验收结果 CSV / JSON、OCR 框选示意图
├── week4_v2/                自包含验证副本（含真实截图，可独立复现）
└── README_私有化部署.md      部署与七类排障
```

## 快速开始

```bash
# 需要 Python 3.11 或 3.12（3.14 下 numpy 导入即报 OverflowError，不可用）
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

pytest src/unit_test -q                 # 24 passed
python tests/acceptance_20cases.py      # 20/20 通过
```

端到端演示（不依赖推理服务，走客户端规则兜底）：

```bash
python client_v2.0.py --offline
# 输入：打开记事本然后输入你好世界
```

接入真实模型时，把 `client_v2.0.py` 的 `SERVER_URL` 改为内网推理服务地址，去掉 `--offline` 直接运行。

## 文档

| 文档 | 内容 |
| --- | --- |
| docs/reports/项目结项报告.docx | 结项主报告，四周过程与量化证据 |
| docs/reports/系统评估报告.docx | 20 条用例逐条结果、覆盖率、显存与耗时分布 |
| docs/reports/架构设计文档.docx | 客户端/服务端分离架构、数据流、接口协议 |
| docs/reports/项目技术总报告.docx | 关键技术选型与实现细节 |
| docs/reports/项目验收自查表.docx | 40 项自查逐项结论 |
| docs/reports/LoRA微调对比报告.docx | 基座与微调输出对比 |
| docs/reports/鲁棒性测试报告.docx | 差分阈值标定、噪声边界、OCR 过滤效果 |
| README_私有化部署.md | 服务端与客户端部署步骤、排障手册 |

## 已知限制

1. **推理服务当前不可达**：原公网隧道已停用，端到端闭环成功样本仅 1 次，且走客户端规则兜底而非模型自主决策。模型自主输出动作协议的成功率尚未统计，不能当作可交付能力。
2. **演示视频未录制**：录制脚本已备（docs/演示视频录制脚本.md），需在 Win11 实机执行。
3. **`ALLOWED_HOSTS` 中残留公网域名**：与“全链路内网”的定位冲突，上线前必须改为内网地址。
4. 动作执行模块的覆盖率缺口集中在真实键鼠设备调用分支，Linux CI 下由替身覆盖，无法计入。

## 环境验证

- 训练与评估：Linux 容器，Python 3.12.11，CUDA 12.8，vGPU 32GB
- 客户端验收：Win11 实机，Python 3.12，真实显示器（无 Xvfb）
- 两平台 20 条用例判定结果完全一致；耗时项强依赖环境，不可跨机器比较绝对值
