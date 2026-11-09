# 中小企业私有化桌面 GUI 智能体 — 部署 README

本 README 面向在企业内网从零部署本系统的工程与运维人员，覆盖服务端（GPU）与客户端（Win11）两侧的完整安装、配置、验证与排障流程。按顺序执行即可，不需要事先理解代码细节。

---

## 1. 系统构成

| 组件 | 位置 | 作用 | 是否必须 |
| --- | --- | --- | --- |
| 推理服务 `server/infer_server.py` | GPU 服务器 | 加载 4bit 基座与 LoRA 适配器，接收截图返回动作 | 必须 |
| 客户端 `client_v2.0.py` | 办公 PC（Win11） | 截图、发请求、执行动作、失败重试 | 必须 |
| 基座模型 Qwen2.5-VL-7B-Instruct | GPU 服务器本地磁盘 | 多模态理解 | 必须 |
| LoRA 适配器（约 19 MiB） | GPU 服务器 | 让模型输出本项目动作格式 | 建议 |
| 训练脚本 `data/finetune/train_lora_qlora.py` | 训练节点 | 产出适配器 | 可选 |

数据流：客户端截图 → JPEG 编码 → 内网 HTTP → 推理服务 → 模型输出一行动作 → 客户端解析 → 安全校验 → 执行 → 截图差分 → 下一轮。

**全链路不出内网**：客户端只上报截图、任务文本与最近 5 条动作历史，不上传任何本地文件内容。

---

## 2. 环境要求

### 2.1 GPU 服务器

| 项目 | 最低 | 推荐 |
| --- | --- | --- |
| GPU 显存 | 16 GB（仅文本场景可 8 GB） | 24 GB 及以上 |
| 内存 | 32 GB | 64 GB |
| 磁盘 | 60 GB（含基座约 16 GB） | 100 GB 以上，模型放数据盘 |
| Python | 3.11 | 3.11 |
| CUDA | 12.1+ | 12.8 |

实测参考环境：PyTorch 2.8.0 / Python 3.12 / CUDA 12.8 / vGPU-32GB / 12 vCPU / 62 GB 内存。7B 模型 4bit 加载后显存分配约 **5.81 GB**；训练时视觉线峰值 **10.96 GB**，纯文本线 **6.34 GB**。

### 2.2 客户端

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10/11（本项目在 Win11 验证） |
| Python | 3.11 及以上 |
| 权限 | 需要能模拟键鼠（部分企业终端有安全软件限制，需加白） |
| 分辨率 | 单显示器；多显示器拼接坐标暂不支持 |

> Python 3.14 环境下 **PaddleOCR 没有可用的 wheel**，因此客户端当前不上本地 OCR，`ocr_text` 传空串。若企业环境为 3.11，可自行接入 PaddleOCR 并复用 `clean_ocr_text`。

---

## 3. 服务端部署

### 3.1 拉取代码与依赖

```bash
git clone https://github.com/xiaobao2099/gui_agent_project.git
cd gui_agent_project

pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
pip install transformers==5.22.1 peft==0.21.2 bitsandbytes==0.50.2 \
            accelerate==1.15.0 qwen-vl-utils==0.0.14 fastapi uvicorn
```

### 3.2 下载基座模型

使用 modelscope（国内网络更稳）：

```bash
pip install modelscope
modelscope download --model Qwen/Qwen2.5-VL-7B-Instruct \
  --local_dir ./models/Qwen--Qwen2.5-VL-7B-Instruct
```

下载完成后目录约 **16 GB**。建议放在数据盘并软链到工作目录，避免系统盘写满（本项目踩过该坑，根分区满会导致加载中途失败）。

### 3.3 启动推理服务

```bash
cd server
python infer_server.py --model ./models/Qwen--Qwen2.5-VL-7B-Instruct \
                       --adapter ./output/lora_adapter \
                       --port 6006
```

启动要点：

1. 必须 4bit 量化加载，否则 16 GB 卡直接 OOM；
2. 关闭思考模式，保证输出是严格单行动作；
3. 若有适配器，启动时挂载；没有适配器也能跑，只是输出格式合规率会明显下降；
4. 首次请求包含模型预热，客户端超时设为 **120 秒**。

### 3.4 服务端自检

```bash
curl -X POST http://127.0.0.1:6006/chat \
  -H "Content-Type: application/json" \
  -d '{"image_b64":"","ocr_text":"","task":"ping","history":[]}'
```

返回字段应为 `{"reply": "..."}`。若返回 404，先确认路由前缀与端口，再确认服务进程是否还在。

### 3.5 进程托管（重要）

SSH 直接 `nohup` 启动的进程在会话断开后会被回收，表现为日志停在半截、服务莫名消失。必须托管：

```bash
# 方式一：screen
screen -S infer
python infer_server.py ...
# Ctrl+A D 脱离

# 方式二：disown
nohup python infer_server.py ... > infer.log 2>&1 &
disown
```

---

## 4. 客户端部署

### 4.1 安装依赖

```cmd
pip install mss pillow requests pynput pyperclip
```

`pyautogui` 仅在部分动作路径使用，若安装失败可先跳过（核心链路不依赖）。

### 4.2 配置服务地址

编辑 `client_v2.0.py` 顶部配置区，**这是唯一需要改的地方**：

```python
SERVER_URL = "http://192.168.10.20:6006/chat"

ALLOWED_HOSTS = ["192.168.10.20", "127.0.0.1", "localhost", "192.168."]
```

> ⚠️ **上线前必改**：仓库当前配置里保留了一个开发阶段的公网隧道域名，与企业内网部署语义冲突。部署到客户环境时**必须删除该条目**，只保留内网 IP 与回环地址，否则出站白名单形同虚设。

### 4.3 启动

```cmd
cd C:\gui-agent
python client_v2.0.py
```

按提示输入任务，例如：

```
打开记事本然后输入你好世界
```

客户端会自动拆成两个子任务依次执行，日志写入 `logs/client_v2.log`。

### 4.4 客户端自检清单

- [ ] 启动后 `logs/` 目录被创建，日志有内容
- [ ] 首轮截图能成功上传（日志无 `推理请求失败`）
- [ ] 模型返回的动作被正确解析（日志有 `[模型] xxx`）
- [ ] 动作执行后日志有 `[执行] ... (差分=...)`
- [ ] 任务结束后进程正常退出，不残留

---

## 5. 关键机制说明（部署时必须知道）

| 机制 | 参数 | 说明与限制 |
| --- | --- | --- |
| 界面差分阈值 | `DIFF_THRESHOLD = 1.2` | 仅在静态全屏直采链路上成立；改用 JPEG 传输或引入动画后必须重新标定 |
| 重试次数 | `MAX_RETRY_PER_ACTION = 2` | 超限跳过并记 error，不会死循环 |
| 子任务轮数上限 | `MAX_ROUNDS_PER_SUBTASK = 12` | 防止模型输出动作导致永不终止 |
| 界面稳定等待 | `SCREEN_STABLE_DELAY = 1.2` 秒 | 低配机器上动画慢，可按需上调 |
| 截图编码 | JPEG q60 | 体积下降一个数量级；有损压缩会引入 4~6 的差分噪声，**不要**用上传图做差分 |
| 动作白名单 | 5 种动作 | `hotkey` / `type` / `click` / `scroll` / `done`，协议外动作直接拒绝 |

**差分只用于判断窗口级动作是否生效**：窗口内输入文字仅产生 0.14 的差分，会被判为未生效，因此 `type` 动作不走差分，直接视为指令已发出。这是已知限制，不是缺陷。

---

## 6. 常见问题排查

### 6.1 `Xlib.error.XauthError`（Linux 侧跑测试）

现象：导入 `pyautogui` / `mouseinfo` 时报 `~/.Xauthority: No such file or directory`。

原因：无物理显示器，缺少 X 会话。

解决：

```bash
xvfb-run -a python -m pytest src/unit_test -q
```

### 6.2 `You cannot perform fine-tuning on purely quantized models`

原因：transformers 5.x 拒绝纯 4bit 模型进 Trainer。

解决：先 `get_peft_model` 挂 LoRA，再交给 Trainer。顺序反了就报这个错。

### 6.3 训练 loss 不动、日志看起来在跑

原因：`datasets.Dataset` 配 transformers 5.x Trainer 会产生空 `epoch_iterator`，不报错但空转。

解决：改用 torch 原生 `Dataset`，设 `remove_unused_columns=False`，自定义 `collate_fn`。

### 6.4 训练第一张图就 OOM

原因：2560×1600 原图直进训练。

解决：`max_pixels=768*768`。代价是损失 UI 细节，需要更粗的动作粒度补偿。

### 6.5 客户端点击位置偏移

原因：物理像素与逻辑像素混用。截图是物理像素，键鼠库用逻辑像素。

解决：所有对外方法统一传物理坐标，由 `physical_to_logical` 内部换算。检查调用方是否误传了逻辑坐标。

### 6.6 模型输出多行或带解释

原因：未关闭思考模式，或适配器未加载。

解决：服务端强制 `enable_thinking=False` 并限制 max_new_tokens；客户端只取第一行，多余内容丢弃。

### 6.7 服务端口能连但全部 404

原因：隧道/端口通，但服务进程已停或路由前缀变了。

解决：先 `curl` 根路径与 `/docs`，再 `ps aux | grep infer_server` 确认进程。

---

## 7. 验证部署是否成功

按三层验证，全部通过才算部署完成：

```bash
# 1. 单元测试（24 条）
xvfb-run -a python -m pytest src/unit_test -q

# 2. 验收用例（20 条）
xvfb-run -a python tests/acceptance_20cases.py

# 3. 覆盖率
xvfb-run -a python -m coverage run --source=src -m pytest src/unit_test -q
python -m coverage report -m
```

预期结果：24 passed；20/20 通过；总覆盖率约 90%。

端到端验证（需 Win11 真机 + 服务在线）：

1. 启动客户端，输入「打开记事本然后输入你好世界」；
2. 观察日志是否依次出现 `hotkey win+r` → `type notepad` → `hotkey enter` → `type 你好世界`；
3. 确认记事本被打开且文字写入；
4. 记录本次耗时与是否一次成功，连续跑 20 次统计成功率。

> 当前基线：端到端闭环在真机成功 1 次（走规则兜底，非模型自主），尚未形成可引用的成功率区间。

---

## 8. 回滚与卸载

系统不写注册表、不装服务、不改系统设置，卸载只需：

```bash
# 客户端
rmdir /s C:\gui-agent

# 服务端
kill <infer_server pid>
rm -rf gui-agent models output
```

客户端产生的全部痕迹限于自身目录下的 `logs/`，不影响操作系统。

---

## 9. 安全须知

1. 客户端必须具备出站白名单，且上线前清除所有公网域名；
2. 客户端 logs 目录可能包含任务文本与窗口标题，按企业数据分级要求管理；
3. 服务端不得暴露到公网，仅监听内网网卡；
4. 高危动作拦截为关键词黑名单，无法覆盖编码混淆，不要把它当作唯一防线；
5. 未经授权的真人声纹/账号自动化不在本系统能力范围内。
