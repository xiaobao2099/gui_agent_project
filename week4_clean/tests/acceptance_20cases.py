# -*- coding: utf-8 -*-
"""
# 第 4 周验收用例执行器（AC-01 ~ AC-20）
#
# 设计原则：
#   1. 每条用例都真实调用 clean_project 中的实现，不使用替身结论；
#   2. 需要键鼠/屏幕的用例，用 monkeypatch 拦截真实设备调用，只校验参数是否正确；
#   3. 每条用例独立计时，输出 success/elapsed，用于统计成功率、耗时与错误率；
#   4. 结果落盘 results.json / results.csv，供报告与图表直接引用。
#
# 运行方式（无桌面环境必须用 Xvfb 提供 DISPLAY）：
#   xvfb-run -a python tests/acceptance_20cases.py
"""
import ctypes
import json
import os
import sys
import time
import traceback
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ---------------------------------------------------------------- #
# Linux 侧导入垫片：client_v2.0.py 面向 Win11，模块级调用了 ctypes.windll
# 与 GetSystemMetrics。此处只补齐这两个符号，使其可被导入并做逻辑级验收。
# ---------------------------------------------------------------- #
class _FakeUser32:
    @staticmethod
    def SetProcessDPIAware():
        return True

    @staticmethod
    def GetSystemMetrics(index):
        return 1920 if index == 0 else 1080


ctypes.windll = types.SimpleNamespace(user32=_FakeUser32)

from PIL import Image  # noqa: E402

from src.perception.perception_engine import PerceptionEngine, get_system_dpi_scale  # noqa: E402
from src.action_executor.action_executor import ActionExecutor  # noqa: E402
from src.agent import GUIAgentLoop  # noqa: E402
import src.action_executor.action_executor as ae_mod  # noqa: E402

# client_v2.0.py 在 __main__ 中动态加载后注入本全局变量
client = None


# ==================================================================== #
# 用例元数据结构：id / 分类 / 名称 / 预期 / 执行函数
# ==================================================================== #
CASES = []


def case(cid, category, name, expected):
    def deco(fn):
        CASES.append({"id": cid, "category": category, "name": name,
                      "expected": expected, "fn": fn})
        return fn
    return deco


# ---------------------------------------------------------------- #
# A 组：桌面感知（AC-01 ~ AC-06）
# ---------------------------------------------------------------- #
@case("AC-01", "感知", "DPI 缩放因子获取", "非 Windows 平台兜底返回 1.0，不抛异常")
def ac01():
    scale = get_system_dpi_scale()
    assert isinstance(scale, float), "返回值类型应为 float"
    assert scale == 1.0, f"Linux 下应为 1.0，实际 {scale}"


@case("AC-02", "感知", "全屏截图捕获", "返回 RGB 图像且尺寸与显示器一致")
def ac02():
    eng = PerceptionEngine(mock_ocr=True)
    img = eng.capture_screen()
    assert isinstance(img, Image.Image), "应返回 PIL Image"
    assert img.mode == "RGB", f"色彩模式应为 RGB，实际 {img.mode}"
    expect_w = eng.sct.monitors[1]["width"]
    assert img.size[0] == expect_w, f"宽度应为 {expect_w}，实际 {img.size[0]}"


@case("AC-03", "感知", "mock 模式不加载 OCR 模型", "reader 为 None，run_ocr 返回空列表")
def ac03():
    eng = PerceptionEngine(mock_ocr=True)
    assert eng.reader is None, "mock 模式不应实例化 OCR 引擎"
    assert eng.run_ocr(Image.new("RGB", (100, 100))) == [], "mock 模式应返回空结果"


class _FakeReader:
    """替身识别器：模拟 easyocr 的 (bbox, text, conf) 返回结构。"""
    def __init__(self, items):
        self.items = items

    def readtext(self, _np_img):
        return self.items


@case("AC-04", "感知", "OCR 置信度过滤", "confidence < 0.6 的识别框被丢弃")
def ac04():
    eng = PerceptionEngine(mock_ocr=True)
    eng.mock_ocr = False
    eng.confidence_thresh = 0.6
    eng.reader = _FakeReader([
        ([[0, 0], [60, 0], [60, 20], [0, 20]], "确定", 0.92),
        ([[0, 30], [60, 30], [60, 50], [0, 50]], "模糊字", 0.41),
        ([[0, 60], [60, 60], [60, 80], [0, 80]], "取消", 0.75),
    ])
    out = eng.run_ocr(Image.new("RGB", (200, 100)))
    texts = [o["text"] for o in out]
    assert texts == ["确定", "取消"], f"低置信框应被剔除，实际保留 {texts}"


@case("AC-05", "感知", "OCR 小尺寸框过滤", "宽或高小于 8 像素的噪声框被丢弃")
def ac05():
    eng = PerceptionEngine(mock_ocr=True)
    eng.mock_ocr = False
    eng.reader = _FakeReader([
        ([[0, 0], [4, 0], [4, 4], [0, 4]], ".", 0.99),        # 宽高均 4，应丢弃
        ([[0, 20], [80, 20], [80, 40], [0, 40]], "记事本", 0.99),
    ])
    out = eng.run_ocr(Image.new("RGB", (200, 100)))
    assert len(out) == 1, f"应只剩 1 个有效框，实际 {len(out)}"
    assert out[0]["text"] == "记事本"


@case("AC-06", "感知", "OCR 结果框绘制与落盘", "输出标注图片文件且非空")
def ac06():
    eng = PerceptionEngine(mock_ocr=True)
    img = Image.new("RGB", (200, 120), "white")
    out_path = os.path.join(ROOT, "test_artifacts", "ocr_bbox_demo.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    eng.draw_ocr_bbox(img, [{"text": "确定", "bbox": [10, 10, 90, 40], "conf": 0.9}], out_path)
    assert os.path.exists(out_path), "标注图片未生成"
    assert os.path.getsize(out_path) > 0, "标注图片为空"


# ---------------------------------------------------------------- #
# B 组：动作执行（AC-07 ~ AC-12）
# ---------------------------------------------------------------- #
class _FakeMouse:
    def __init__(self):
        self.position = None
        self.clicks = []

    def click(self, btn, n=1):
        self.clicks.append((self.position, n))


class _FakeKeyboard:
    def __init__(self):
        self.typed = []

    def type(self, text):
        self.typed.append(text)


@case("AC-07", "动作", "物理像素→逻辑像素坐标换算", "DPI=1.0 时坐标原样返回")
def ac07():
    ex = ActionExecutor()
    lx, ly = ex.physical_to_logical(1200, 800)
    assert (lx, ly) == (1200, 800), f"DPI=1.0 应原样返回，实际 {(lx, ly)}"


@case("AC-08", "动作", "点击动作参数传递", "鼠标定位到换算后坐标并单击 1 次")
def ac08():
    ex = ActionExecutor()
    ex.mouse = _FakeMouse()
    ex.click(300, 200, button="left", clicks=1)
    assert ex.mouse.position == (300, 200), f"定位坐标错误：{ex.mouse.position}"
    assert ex.mouse.clicks == [((300, 200), 1)], f"点击次数错误：{ex.mouse.clicks}"


@case("AC-09", "动作", "中文文本输入经剪贴板", "文本写入剪贴板后以 Ctrl+V 粘贴")
def ac09():
    ex = ActionExecutor()
    copied = []
    pressed = []

    ex.keyboard = _FakeKeyboard()
    ex.keyboard.press = lambda k: pressed.append(("press", str(k)))
    ex.keyboard.release = lambda k: pressed.append(("release", str(k)))

    import pyperclip
    orig_copy = pyperclip.copy
    pyperclip.copy = lambda t: copied.append(t)
    try:
        ex.type_text("你好世界")
    finally:
        pyperclip.copy = orig_copy
    assert copied == ["你好世界"], f"未走剪贴板：{copied}"
    assert any("press" in p for p in pressed), "未触发粘贴快捷键"


@case("AC-10", "动作", "组合快捷键执行", "hotkey 按顺序传入 ctrl,c")
def ac10():
    ex = ActionExecutor()
    recorded = []
    orig = ae_mod.pyautogui

    class _FakePyAutoGUI:
        FAILSAFE = True
        PAUSE = 0.3

        @staticmethod
        def hotkey(*keys):
            recorded.append(keys)

    ae_mod.pyautogui = _FakePyAutoGUI()
    try:
        ex.hotkey("ctrl", "c")
    finally:
        ae_mod.pyautogui = orig
    assert recorded == [("ctrl", "c")], f"快捷键参数错误：{recorded}"


@case("AC-11", "动作", "高危动作关键词拦截", "type 含 rm 等关键词抛 RuntimeError")
def ac11():
    ex = ActionExecutor()
    try:
        ex.execute_action({"action": "type", "text": "rm -rf /tmp/data"})
    except RuntimeError as e:
        assert "禁止关键词" in str(e), f"拦截原因不明确：{e}"
        return
    raise AssertionError("高危文本未被拦截")


@case("AC-12", "动作", "未知动作类型拒绝", "不在协议内的动作抛 NotImplementedError")
def ac12():
    ex = ActionExecutor()
    try:
        ex.execute_action({"action": "open_url", "url": "http://x"})
    except NotImplementedError as e:
        assert "open_url" in str(e), f"异常信息应含动作名：{e}"
        return
    raise AssertionError("未知动作未被拒绝")


# ---------------------------------------------------------------- #
# C 组：Agent 调度（AC-13 ~ AC-16）
# ---------------------------------------------------------------- #
@case("AC-13", "调度", "三类意图规划映射", "点击/回车/输入分别映射到 click、hotkey、type")
def ac13():
    loop = GUIAgentLoop()
    p1 = loop.run_step("点击页面按钮")["plan"]
    p2 = loop.run_step("按下回车")["plan"]
    p3 = loop.run_step("输入测试文本")["plan"]
    assert p1[0]["tool"] == "action_click", p1
    assert p2[0]["tool"] == "action_hotkey", p2
    assert p3[0]["tool"] == "action_type", p3


@case("AC-14", "调度", "空规划终止循环", "无匹配意图时规划为空且单轮即停")
def ac14():
    loop = GUIAgentLoop()
    res = loop.run_step("随便聊点别的")
    assert res["plan"] == [], f"应无规划，实际 {res['plan']}"
    history = loop.run("随便聊点别的", max_round=3)
    assert len(history) == 1, f"空规划应一轮终止，实际 {len(history)} 轮"


@case("AC-15", "调度", "多轮循环上限保护", "长任务最多执行 max_round 轮")
def ac15():
    loop = GUIAgentLoop()
    history = loop.run("点击页面按钮", max_round=2)
    assert len(history) == 2, f"应恰好执行 2 轮，实际 {len(history)}"


@case("AC-16", "调度", "工具路由返回结构", "每条执行结果含 tool/args/ret 且 status=ok")
def ac16():
    loop = GUIAgentLoop()
    res = loop.run_step("点击页面按钮")
    assert len(res["execute"]) == 1
    item = res["execute"][0]
    for key in ("tool", "args", "ret"):
        assert key in item, f"缺少字段 {key}"
    assert item["ret"]["status"] == "ok", item["ret"]


# ---------------------------------------------------------------- #
# D 组：鲁棒性（AC-17 ~ AC-20）
# ---------------------------------------------------------------- #
@case("AC-17", "鲁棒性", "复合指令长任务拆解", "按连接词切成有序子任务，无连接词保持单条")
def ac17():
    parts = client.split_subtasks("打开记事本然后输入你好世界")
    assert parts == ["打开记事本", "输入你好世界"], f"拆解结果错误：{parts}"
    single = client.split_subtasks("打开记事本")
    assert single == ["打开记事本"], f"单任务不应拆分：{single}"


@case("AC-18", "鲁棒性", "动作协议解析容错", "合法格式解析成功，非法/残缺格式返回 None 不抛异常")
def ac18():
    assert client.parse_action("click 300,500")["x"] == 300
    assert client.parse_action("type notepad")["text"] == "notepad"
    assert client.parse_action("done")["action"] == "done"
    assert client.parse_action("这不是协议格式") is None, "非协议文本应返回 None"
    assert client.parse_action("click abc,def") is None, "残缺坐标应返回 None 而非抛异常"


@case("AC-19", "鲁棒性", "OCR 噪声文本过滤", "空行、单字符、纯符号、重复行被剔除，正文保留")
def ac19():
    raw = "记事本\n\nA\n!!!\n记事本\n你好世界\n  \n@#$"
    cleaned = client.clean_ocr_text(raw)
    assert cleaned == "记事本\n你好世界", f"过滤结果错误：{cleaned!r}"
    assert client.clean_ocr_text("") == "", "空输入应返回空串"


@case("AC-20", "鲁棒性", "界面差分阈值判定（真实截图）", "跨窗口跳变判为已变化，窗口内文字输入判为无变化")
def ac20():
    real_dir = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "realdata")
    p0 = os.path.join(real_dir, "img_0.png")
    p1 = os.path.join(real_dir, "img_1.png")
    p2 = os.path.join(real_dir, "img_2.png")
    p3 = os.path.join(real_dir, "img_3.png")
    if not all(os.path.exists(p) for p in (p0, p1, p2, p3)):
        raise AssertionError(f"真实截图缺失，未找到：{real_dir}")

    def thumb(path):
        # 与生产实现一致：RGB → 160×90 → 灰度
        return Image.open(path).convert("RGB").resize((160, 90)).convert("L")

    # 相邻帧 img_0(桌面) → img_1(运行框弹出)：全屏级跳变
    changed, score = client.changed_more_than(thumb(p0), thumb(p1))
    assert changed is True, f"跨窗口跳变应判为已变化，实际差分 {score}"
    assert 6.0 < score < 12.0, f"跨窗口差分应处 6~12 区间，实际 {score}"

    changed2, score2 = client.changed_more_than(thumb(p2), thumb(p3))
    assert changed2 is False, f"窗口内文字输入应判为无变化（已知漏检），实际差分 {score2}"
    assert score2 < 1.2, f"文字输入差分应低于阈值，实际 {score2}"


# ==================================================================== #
# 执行器：逐条运行、独立计时、结果落盘
# ==================================================================== #
def main():
    results = []
    print("=" * 78)
    print("第 4 周验收用例执行（AC-01 ~ AC-20）")
    print("=" * 78)
    for c in CASES:
        t0 = time.perf_counter()
        try:
            c["fn"]()
            ok, err = True, ""
        except Exception as e:
            ok, err = False, f"{type(e).__name__}: {e}"
            traceback.print_exc()
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        results.append({
            "id": c["id"], "category": c["category"], "name": c["name"],
            "expected": c["expected"], "passed": ok,
            "elapsed_ms": elapsed_ms, "error": err,
        })
        print(f"[{'PASS' if ok else 'FAIL'}] {c['id']} {c['name']}  ({elapsed_ms} ms)"
              + (f"  <- {err}" if not ok else ""))

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    elapsed_all = sum(r["elapsed_ms"] for r in results)
    avg_ms = round(elapsed_all / total, 2)
    max_ms = max(r["elapsed_ms"] for r in results)
    min_ms = min(r["elapsed_ms"] for r in results)

    summary = {
        "total": total, "passed": passed, "failed": failed,
        "pass_rate": round(passed / total * 100, 2),
        "error_rate": round(failed / total * 100, 2),
        "avg_ms": avg_ms, "max_ms": max_ms, "min_ms": min_ms,
        "total_ms": round(elapsed_all, 2),
        "executed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "env": f"Python {sys.version.split()[0]} / {sys.platform} / Xvfb",
    }

    print("-" * 78)
    print(f"用例总数 {total} / 通过 {passed} / 失败 {failed} / 通过率 {summary['pass_rate']}%")
    print(f"总耗时 {summary['total_ms']} ms / 平均 {avg_ms} ms / 最长 {max_ms} ms")

    out_dir = os.path.join(ROOT, "test_artifacts")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "cases": results}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "results.csv"), "w", encoding="utf-8") as f:
        f.write("id,category,name,passed,elapsed_ms,error\n")
        for r in results:
            f.write(f"{r['id']},{r['category']},{r['name']},{r['passed']},{r['elapsed_ms']},{r['error']}\n")
    print(f"结果已写入 {out_dir}/results.json 与 results.csv")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    # 以模块名方式加载 client_v2.0.py（文件名含点号，无法直接 import）
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "client_v2_0_proxy", os.path.join(ROOT, "client_v2.0.py"))
    client = importlib.util.module_from_spec(spec)
    sys.modules["client_v2_0_proxy"] = client
    spec.loader.exec_module(client)
    globals()["client"] = client
    sys.exit(main())
