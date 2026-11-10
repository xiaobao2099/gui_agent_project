# -*- coding: utf-8 -*-
"""
================================================================================
中小企业私有化桌面 GUI 智能体 v2.0 —— Win11 瘦客户端（鲁棒性增强版）
--------------------------------------------------------------------------------
职责(本地端, 不做推理):
  1. mss 全屏截图 -> base64
  2. POST 到内网 GPU 推理服务, 得到下一步动作
  3. pynput 逐步执行动作(每轮只执行第一行)
  4. 鲁棒性增强(v2.0):
       - 长任务自动拆解为子任务, 逐段完成
       - 动作失败检测: 执行前后截图差分, 界面无变化则判定失败并重试
       - 同一动作最多自动重试 N 次, 超限跳过并记录, 不死循环
       - OCR 文本噪声过滤(接口预留, 当前无 OCR 引擎也可运行)
       - 安全层: 出站请求白名单 + 动作白名单 + 本地日志, 不向外发送文件内容
依赖: pip install mss pillow requests pynput
运行: python client_v2.0.py            正常模式, 走 GPU 推理服务
      python client_v2.0.py --offline    离线演示模式, 不联网, 走规则兜底序列(仅用于无服务环境下录制演示)
================================================================================
"""

import os
import io
import re
import sys
import time
import base64
import logging
import requests
import ctypes

import mss
import pynput
from PIL import Image, ImageChops, ImageStat
from pynput.mouse import Button
from pynput.keyboard import Key

# ============================ 配置区(可替换) ============================
# 推理服务地址: 部署到企业内网后仅需改此处, 例如 http://192.168.x.x:6006/chat
SERVER_URL = "https://u1145783-vrdd-4e26273a.weste.seetacloud.com:8443/chat"

# --- 安全白名单: 只允许向这些域名/地址发请求, 防止误连外网 ---
ALLOWED_HOSTS = ["u1145783-vrdd-4e26273a.weste.seetacloud.com", "127.0.0.1", "localhost", "192.168."]
# --- 动作白名单: 模型输出不在此列直接拒绝, 杜绝任意命令/路径执行 ---
ALLOWED_ACTIONS = {"hotkey", "type", "click", "scroll", "done"}

MAX_RETRY_PER_ACTION = 2        # 同一动作失败后最多重试次数
MAX_ROUNDS_PER_SUBTASK = 12     # 单个子任务最大循环轮数
SCREEN_STABLE_DELAY = 1.2       # 每步执行后等待界面稳定秒数
DIFF_THRESHOLD = 1.2            # 差分均值阈值(灰度), 低于该值判定界面无变化=动作未生效

# 本地日志(纯本地保存, 不外传)
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "client_v2.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("gui-agent")

# ============================ 截图环境初始化 ============================
# DPI 感知, 避免高缩放屏下截图分辨率错位
ctypes.windll.user32.SetProcessDPIAware()
user32 = ctypes.windll.user32
SCREEN = {"top": 0, "left": 0,
          "width": user32.GetSystemMetrics(0),
          "height": user32.GetSystemMetrics(1)}

sct = mss.mss()
mouse = pynput.mouse.Controller()
keyboard = pynput.keyboard.Controller()

KEY_MAP = {
    "win": Key.cmd, "ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift,
    "enter": Key.enter, "esc": Key.esc, "tab": Key.tab, "space": Key.space,
    "backspace": Key.backspace, "delete": Key.delete, "home": Key.home,
    "end": Key.end, "pageup": Key.page_up, "pagedown": Key.page_down,
}


# ============================ 安全层 ============================
def safe_request(url, payload, timeout=120):
    """出站请求安全校验: 仅允许白名单主机。"""
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
    if not any(host == h or host.startswith(h) for h in ALLOWED_HOSTS):
        log.error("安全拦截: 请求主机不在白名单 -> %s", host)
        raise PermissionError(f"host not allowed: {host}")
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def sanitize_action(act_dict):
    """动作安全校验: 动作类型必须在白名单; type 内容长度限制; 禁止路径/命令关键字。"""
    act = act_dict.get("action")
    if act not in ALLOWED_ACTIONS:
        return False, f"动作 {act} 不在白名单, 已拒绝"
    text = str(act_dict.get("text", ""))
    # 拒绝可疑命令串(安全审查项: 不执行 shell/路径类指令)
    banned = ["cmd", "powershell", "rm ", "del ", "http://", "https://", "C:\\", "D:\\"]
    if any(b in text.lower() for b in banned):
        return False, f"动作文本含可疑内容, 已拒绝: {text!r}"
    if act == "type" and len(text) > 200:
        return False, "type 文本过长, 已截断保护"
    return True, "ok"


# ============================ OCR 噪声过滤(预留接口) ============================
def clean_ocr_text(raw):
    """对 OCR 文本做噪声清洗: 去空行/重复行/单字符噪声/纯符号行。
    当前本机无 OCR 引擎(Windows Python 3.14 无 paddle wheel), ocr_text 默认空字符串;
    后续接入 EasyOCR 或云端 OCR 时直接复用本函数。"""
    if not raw:
        return ""
    lines, seen = [], set()
    for line in raw.splitlines():
        line = re.sub(r"[\s]+", " ", line).strip()
        if len(line) <= 1:                       # 单字符噪声
            continue
        if re.fullmatch(r"[\W_]+", line):       # 纯符号噪声
            continue
        if line in seen:                        # 重复行去重
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines)


# ============================ 长任务拆解 ============================
def split_subtasks(task):
    """复合指令拆解: 按连接词切分为子任务序列, 逐段执行, 降低模型一次规划过长的失败率。"""
    parts = re.split(r"然后|接着|之后|再|并且|并|;|；", task)
    parts = [p.strip(" ，,。") for p in parts if p.strip()]
    return parts if len(parts) > 1 else [task]


# ============================ 截图与差分(失败检测) ============================
def grab_thumb():
    """抓当前屏幕并缩成小灰度图, 用于执行前后差分比较。"""
    raw = sct.grab(SCREEN)
    img = Image.frombytes("RGB", raw.size, raw.rgb)
    return img.resize((160, 90)).convert("L")


def changed_more_than(before, after, threshold=DIFF_THRESHOLD):
    """比较两张缩略图的像素平均差异, 返回(是否变化, 差异值)。"""
    diff = ImageChops.difference(before, after)
    stat = ImageStat.Stat(diff)
    mean_diff = sum(stat.mean) / len(stat.mean)
    return mean_diff > threshold, round(mean_diff, 2)


def screenshot_b64():
    raw = sct.grab(SCREEN)
    img = Image.frombytes("RGB", raw.size, raw.rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    return base64.b64encode(buf.getvalue()).decode()


# ============================ 动作解析(统一空格格式, 兼容旧变体) ============================
def parse_action(text):
    text = text.strip()
    # 空格格式: hotkey win+r / type notepad / click 300,500
    parts = text.split(" ", 1)
    act = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    if act == "hotkey":
        return {"action": "hotkey", "x": 0, "y": 0, "text": arg}
    if act == "type":
        return {"action": "type", "x": 0, "y": 0, "text": arg}
    if act == "scroll":
        return {"action": "scroll", "x": 0, "y": 0, "text": ""}
    if act == "click":
        # 坐标容错: 模型可能输出 "click 300,500" 或残缺坐标, 解析失败返回 None 交由上层跳过
        try:
            x_str, y_str = arg.replace(" ", "").split(",")
            return {"action": "click", "x": int(x_str), "y": int(y_str), "text": ""}
        except (ValueError, IndexError):
            return None
    if act == "done":
        return {"action": "done", "x": 0, "y": 0, "text": ""}
    return None


# ============================ 动作执行 ============================
def execute(action_dict):
    act = action_dict.get("action")
    if act == "click":
        x, y = int(action_dict.get("x", 0)), int(action_dict.get("y", 0))
        mouse.position = (x, y)
        time.sleep(0.1)
        mouse.click(Button.left, 1)
    elif act == "type":
        keyboard.type(action_dict.get("text", ""))
    elif act == "hotkey":
        text = str(action_dict.get("text", "")).lower()
        if not text:
            return False
        combo = text.split("+")
        pressed = [KEY_MAP.get(k, k) for k in combo]
        for k in pressed:
            keyboard.press(k)
            time.sleep(0.05)
        time.sleep(0.08)
        for k in reversed(pressed):
            keyboard.release(k)
            time.sleep(0.05)
        if len(pressed) == 1:
            time.sleep(0.1)
    elif act == "scroll":
        mouse.scroll(0, -3)
    elif act == "done":
        return True
    return False


# ============================ 单子任务执行(含失败检测与重试) ============================
def fallback_actions(text):
    """规则兜底(演示用): 模型未输出一行协议动作时, 按关键词映射固定动作序列。
    这是临时闭环手段, 非模型自主决策; 正式版本靠 LoRA 扩样本学会协议后移除。"""
    t = text.lower()
    acts = []
    if "记事本" in text or "notepad" in t:
        acts += [{"action": "hotkey", "x": 0, "y": 0, "text": "win+r"},
                 {"action": "type", "x": 0, "y": 0, "text": "notepad"},
                 {"action": "hotkey", "x": 0, "y": 0, "text": "enter"}]
    if "你好世界" in text:
        acts.append({"action": "type", "x": 0, "y": 0, "text": "你好世界"})
    return acts


def do_action(action):
    """安全校验 + 执行 + 差分失败检测 + 自动重试, 返回是否成功。"""
    ok, msg = sanitize_action(action)
    if not ok:
        log.warning(msg)
        return False
    for retry in range(MAX_RETRY_PER_ACTION + 1):
        before = grab_thumb()
        execute(action)
        time.sleep(SCREEN_STABLE_DELAY)
        after = grab_thumb()
        if action.get("action") == "type":      # 文本动作不易差分, 直接视为已发出
            return True
        changed, score = changed_more_than(before, after)
        log.info("[执行] %s (差分=%.2f, 重试=%d)", action, score, retry)
        if changed:
            return True
        log.warning("动作未生效(界面无变化), 重试 %d/%d", retry + 1, MAX_RETRY_PER_ACTION)
        time.sleep(0.6)
    log.error("动作多次失败, 跳过: %s", action)
    return False


def run_subtask(subtask, global_history, offline=False):
    history = list(global_history)

    # ---- 离线演示模式: 不发任何请求, 直接按关键词规则执行 ----
    # 仅用于推理服务不可达时录制端到端演示; 日志会显式标注, 不冒充模型决策
    if offline:
        seq = fallback_actions(subtask)
        if not seq:
            log.warning("离线模式未匹配到规则动作, 跳过子任务: %s", subtask)
            return history
        log.warning("离线演示模式: 跳过推理请求, 规则兜底序列 = %s",
                    [a.get("text") or a.get("action") for a in seq])
        for a in seq:
            if a.get("action") == "done":
                break
            do_action(a)
            history.append(f"{a.get('action')} {a.get('text','')}".strip())
        return history

    for step in range(MAX_ROUNDS_PER_SUBTASK):
        log.info("---- 子任务[%s] 第%d轮 ----", subtask, step + 1)
        img_b64 = screenshot_b64()
        try:
            reply = safe_request(SERVER_URL, {
                "image_b64": img_b64,
                "ocr_text": clean_ocr_text(""),     # 预留: 接入 OCR 后填入识别文本
                "task": subtask,
                "history": history[-5:],
            })["reply"]
        except Exception as e:
            log.error("推理请求失败: %s", e)
            return history
        log.info("[模型] %s", reply)

        lines = [l.strip() for l in reply.replace("```", "").split("\n") if l.strip()]
        if not lines:
            break
        action = parse_action(lines[0])           # 每轮只取第一行, 逐步决策

        # 模型未输出协议动作 -> 走规则兜底序列
        if action is None:
            seq = fallback_actions(lines[0])
            if not seq:
                log.warning("模型输出非协议动作, 安全跳过: %s", lines[0]); break
            log.warning("模型输出非协议, 启用规则兜底序列: %s",
                        [a.get("text") or a.get("action") for a in seq])
        else:
            seq = [action]

        for a in seq:
            if a.get("action") == "done":
                log.info("子任务完成: %s", subtask)
                break
            do_action(a)
            history.append(f"{a.get('action')} {a.get('text','')}".strip())

        if action is None:
            break        # 兜底序列一轮内执行完毕, 结束本子任务

    return history


# ============================ 主流程 ============================
def main():
    offline = "--offline" in sys.argv
    if offline:
        log.warning("==== 离线演示模式(规则兜底, 非模型自主决策, 不发送任何推理请求) ====")
    task = input("请输入任务: ").strip()
    if not task:
        return
    subtasks = split_subtasks(task)
    log.info("长任务拆解为 %d 个子任务: %s", len(subtasks), subtasks)

    global_history = []
    for sub in subtasks:
        log.info("==== 开始子任务: %s ====", sub)
        global_history = run_subtask(sub, global_history, offline=offline)
    log.info("全部子任务执行结束。")


if __name__ == "__main__":
    main()
