# -*- coding: utf-8 -*-
"""
================================================================================
 FaceGuard 酱 —— 二次元风护眼距离提醒小工具（单文件版）
================================================================================
 【功能一句话】
   读取本机摄像头 → 本地人脸检测（OpenCV Haar 级联）→ 实时跟踪"人脸占画面比例"。
   当人脸持续变大（= 头不断向屏幕凑近）超过设定阈值、且连续多帧确认后，触发提醒：
   二次元弹窗 + 可选屏幕角落悬浮字幕 + 可选提示音。冷却时间内不会重复报警。

 【隐私承诺（硬性要求）】
   * 全程离线：代码中没有任何网络请求，运行时绝不联网下载模型/上传数据；
   * 人脸模型 haarcascade_frontalface_default.xml 随程序打包内置（见 build.bat）；
   * 摄像头画面只在本机内存中实时处理，不写文件、不上传任何服务器，关闭即消失。

 【技术选型（为什么这样选）】
   * GUI      : Tkinter —— Python 标准库，零额外依赖，PyInstaller 打包体积最小；
   * 人脸检测 : OpenCV 自带 Haar 级联 —— 比 MTCNN 轻量几个数量级（模型 <1MB），
                CPU 单线程即可 30FPS 实时，且 XML 直接内置在 opencv 包里可随包打包；
   * 显示辅助 : Pillow —— 仅用于把 OpenCV 帧高效刷到 Tkinter 画布（不走 PNG 编码）。

 【运行】   python face_guard.py
 【打包】   双击 build.bat（或看 README.md 中的完整命令与注意事项）
================================================================================
"""

import os
import sys
import time
import queue
import random
import platform
import threading
import traceback

# ---------------- 第三方依赖（pip install opencv-python-headless pillow） ----------------
import cv2
import numpy as np                 # OpenCV 依赖，显式引入便于阅读
from PIL import Image, ImageTk     # 仅用于界面显示，不参与任何算法

IS_WINDOWS = (platform.system() == "Windows")

# Windows 下开启 DPI 感知，高分屏上界面文字不模糊（失败也不影响运行）
if IS_WINDOWS:
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        import winsound            # Windows 自带，用于提示音，非 Windows 自动跳过
    except ImportError:
        winsound = None

import tkinter as tk
from tkinter import ttk, messagebox

# ================================ 常量与文案 ================================

APP_NAME = "FaceGuard 酱"
APP_VERSION = "v1.0"

# 内置人脸检测模型文件名（打包时用 --add-data 塞进 EXE，见 build.bat）
CASCADE_FILENAME = "haarcascade_frontalface_default.xml"

# 弹窗文案：(大字颜文字, 正文)。每次报警随机抽一条，避免视觉疲劳
POPUP_TEXTS = [
    ("(＞﹏＜) 距离太近啦！",
     "脸都要贴到屏幕上了说！\n对眼睛和颈椎都很不友好的喵～\n建议保持 50~70cm 的距离哦 (๑•̀ㅂ•́)و✧"),
    ("(╬ Ò﹏Ó) 护眼结界触发！",
     "检测到程序员正在向屏幕坠落……\n快退后！代码又不会跑掉啦！(ﾉ≧∀≦)ﾉ"),
    ("(｡•́︿•̀｡) 有点太近了喵……",
     "屏幕距离过近会加重视疲劳哦～\n去接杯水休息 20 秒，回来继续肝！(๑•̀ㅁ•́๑)✧"),
    ("(ﾟДﾟ≡ﾟДﾟ) 警告！警告！",
     "人脸尺寸超标！已进入【贴脸码字】状态～\n退后一步，海阔天空 (っ•̀ω•́)っ✨"),
]

# 屏幕角落悬浮字幕（短句）
FLOAT_TEXTS = [
    "太近啦！(＞﹏＜)",
    "退后一点嘛～(´･ω･`)",
    "护眼提醒：离屏幕远一点！",
    "贴脸警告 (╬ Ò﹏Ó)",
    "眼睛：救命！(；´д｀)",
]

# 状态栏文案：(文字, 颜色)
STATE_TEXT = {
    "noface":   ("画面里没有人脸……人呢？(・_・;)", "#868e96"),
    "far":      ("脸有点远呀，检测不到稳定人脸 (´･ω･`)", "#868e96"),
    "normal":   ("距离正常，继续加油写代码！(๑•̀ㅂ•́)و✧", "#2f9e44"),
    "near":     ("有点近了哦……再近就要报警啦 (￣^￣)", "#f59f00"),
    "cooldown": ("冷却中……刚刚提醒过啦，快退后呀 (´･ω･`)", "#f59f00"),
    "alert":    ("太近啦！！(╬ Ò﹏Ó)", "#e03131"),
}

# 字体（Windows 用微软雅黑，其它系统自动回退到默认字体）
_FONT = "Microsoft YaHei UI" if IS_WINDOWS else "Helvetica"
FONT_UI    = (_FONT, 10)
FONT_SMALL = (_FONT, 9)
FONT_BTN   = (_FONT, 11, "bold")
FONT_TITLE = (_FONT, 16, "bold")
FONT_POP   = (_FONT, 22, "bold")


# ================================ 工具函数 ================================

def app_dir():
    """程序所在目录。
    PyInstaller --onefile 打包后，sys.executable 才是 EXE 真实路径
    （__file__ 会被解压到临时目录），所以日志等文件要写到 EXE 旁边。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def log_error(detail):
    """把异常写入 EXE 同目录的日志文件。--windowed 打包后没有控制台，
    这是排错（尤其"双击没反应"）的唯一线索。"""
    try:
        with open(os.path.join(app_dir(), "face_guard_error.log"), "a", encoding="utf-8") as f:
            f.write("\n[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), detail))
    except Exception:
        pass


def find_cascade_path():
    """定位内置 Haar 人脸模型，按优先级尝试多个位置：
    1. PyInstaller 解包目录 sys._MEIPASS（--onefile 打包后 --add-data 的文件在这里）
    2. opencv 包自带的 cv2.data.haarcascades（开发环境直接跑 python face_guard.py）
    3. 兜底：cv2 包目录下找 data 子目录
    全都找不到返回 None（会弹窗报错，绝不联网去下载）。
    """
    if getattr(sys, "frozen", False):                       # 打包后
        cand = os.path.join(sys._MEIPASS, CASCADE_FILENAME)
        if os.path.exists(cand):
            return cand
    try:                                                    # 开发环境：pip 安装的 opencv
        cand = os.path.join(cv2.data.haarcascades, CASCADE_FILENAME)
        if os.path.exists(cand):
            return cand
    except Exception:
        pass
    cand = os.path.join(os.path.dirname(cv2.__file__), "data", CASCADE_FILENAME)
    if os.path.exists(cand):
        return cand
    return None


# ================================ 靠近判定引擎 ================================

class ProximityEngine:
    """靠近判定引擎：EMA 平滑 + 自适应基线 + 连续帧确认 + 冷却。

    为什么这样设计（抗晃动 / 抗误报）：
    1. fast EMA(α=0.35) 平滑"人脸宽度占比"：抹平单帧检测框抖动，
       打喷嚏/挥手造成的一帧突变会被曲线稀释，几乎不动；
    2. slow EMA(α=0.02) 维护"正常坐姿基线"：人总会慢慢挪动，基线跟着慢速漂移，
       避免"坐姿渐变"被误判成"靠近"；
    3. 只有当【平滑值 / 基线】≥ 触发阈值，且连续 confirm 帧都满足，才报警
       —— 偶尔一两帧凑近（拿水杯）不会触发；
    4. 触发后进入冷却：冷却时间内即使仍贴近也只算 near，不重复报警；
       冷却结束后若仍然贴近，会再提醒一次（防止被无视）；
    5. 处于"贴近区"时冻结基线更新，防止一直贴脸把基线也抬高、
       导致之后永远不再报警。
    """

    ALPHA_FAST = 0.35   # 快速平滑系数：越大跟随越快、抗抖越弱
    ALPHA_SLOW = 0.02   # 基线漂移系数：越小基线越稳定

    def __init__(self):
        self._smoothed = None    # 平滑后的人脸宽度占比
        self._baseline = None    # "正常坐姿"基线占比
        self._streak = 0         # 连续"过近"帧计数
        self._next_fire = 0.0    # 冷却结束时间戳
        self._closeness = 0.0    # 当前 平滑值/基线，供 UI 展示

    def reset(self):
        self._smoothed = None
        self._baseline = None
        self._streak = 0
        self._next_fire = 0.0
        self._closeness = 0.0

    def miss(self):
        """本帧没检测到（稳定）人脸：连续计数清零（突变断链），基线保留。
        短暂遮挡不重学基线，所以晃出画面再回来不会误触发。"""
        self._streak = 0

    def closeness(self):
        return self._closeness

    def update(self, size_ratio, threshold, confirm_frames, cooldown_sec, allow_fire=True):
        """输入本帧人脸宽度占比（0~1），返回 (状态, 是否冷却中)。
        状态: "normal" 正常 / "near" 接近 / "fire" 触发报警（本帧刚好命中）"""
        now = time.time()
        if self._smoothed is None:
            # 第一帧：直接作为初始基线（开机时你坐的位置 = 你的正常距离）
            self._smoothed = size_ratio
            self._baseline = size_ratio
        else:
            self._smoothed += self.ALPHA_FAST * (size_ratio - self._smoothed)
        self._closeness = self._smoothed / max(self._baseline, 1e-6)

        if self._closeness >= threshold:
            # ---- 进入"贴近区"：基线冻结，只累计连续帧 ----
            self._streak += 1
            if (self._streak >= confirm_frames and allow_fire
                    and now >= self._next_fire):
                self._next_fire = now + cooldown_sec   # 触发即进入冷却
                return "fire", True
            return "near", now < self._next_fire

        # ---- 正常区：基线慢速跟随新坐姿，计数清零 ----
        self._baseline += self.ALPHA_SLOW * (self._smoothed - self._baseline)
        self._streak = 0
        return "normal", False


# ================================ 摄像头后台线程 ================================

class CameraWorker(threading.Thread):
    """后台线程：抓帧 → 人脸检测 → 靠近判定 → 画框 → 写入共享状态。

    为什么单独开线程：cv2.VideoCapture.read() 和 Haar 检测都是阻塞操作，
    放主线程会卡死 Tkinter 界面；分开后即使主窗口最小化，检测也在后台继续跑，
    报警弹窗照常弹出（满足"最小化后继续检测"）。
    """

    DETECT_WIDTH   = 320    # 检测前把画面宽度缩到 320px：Haar 耗时近似正比于像素数，
                            # 320 宽下单帧约 5~15ms，CPU 占用极低
    MIN_FACE_RATIO = 0.08   # 人脸宽度 < 画面 8% 视为"太远"：远处小脸检测噪声大，
                            # 不参与靠近判定，也避免把背景路人算进来
    WARMUP_SEC     = 2.0    # 启动后 2 秒内不报警：给基线留出学习"正常坐姿"的时间
    MAX_READ_FAIL  = 30     # 连续读取失败约 1 秒后判定摄像头异常

    def __init__(self, cam_index, shared, events, get_params):
        super().__init__(daemon=True, name="CameraWorker")
        self.cam_index  = cam_index
        self.shared     = shared       # dict: lock / frame / metrics（线程间共享）
        self.events     = events       # queue.Queue：向 UI 线程投递一次性事件
        self.get_params = get_params   # 回调：实时获取滑块参数（UI 侧保证线程安全）
        self._stop      = threading.Event()
        self.detector   = None

    def stop(self):
        self._stop.set()

    # ---------- 子步骤 ----------

    def _fatal(self, msg):
        self.events.put(("fatal", msg))

    def _load_model(self):
        """加载内置 Haar 模型。找不到/加载失败 → 报错退出，绝不联网下载。"""
        path = find_cascade_path()
        if path is None:
            self._fatal(
                "找不到人脸检测模型 %s！\n\n"
                "开发运行：请 pip install opencv-python-headless\n"
                "打包运行：打包命令必须带\n"
                "  --add-data \"<opencv的data目录>\\%s;.\"" % (CASCADE_FILENAME, CASCADE_FILENAME))
            return None
        detector = cv2.CascadeClassifier(path)
        if detector.empty():
            self._fatal("人脸模型加载失败：%s" % path)
            return None
        self.detector = detector
        return path

    def _open_camera(self):
        """打开摄像头。Windows 下优先 CAP_DSHOW：打开速度快（避开 MSMF 的
        数秒超时），兼容性更好；失败再兜底用默认后端。"""
        api_pref = cv2.CAP_DSHOW if IS_WINDOWS else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.cam_index, api_pref)
        if not cap.isOpened() and api_pref != cv2.CAP_ANY:
            cap.release()
            cap = cv2.VideoCapture(self.cam_index, cv2.CAP_ANY)
        if not cap.isOpened():
            self._fatal(
                "无法打开摄像头（设备 %d）！\n\n"
                "请依次检查：\n"
                "  1. 摄像头是否被其他软件占用（腾讯会议/钉钉/OBS 等）\n"
                "  2. Windows 设置 → 隐私和安全性 → 相机 → 允许桌面应用访问相机\n"
                "  3. 笔记本是否有物理摄像头开关 / Fn 快捷键\n"
                "  4. 外接摄像头请试试把界面上的【设备编号】改成 1 或 2" % self.cam_index)
            return None
        # 限制分辨率：检测用不到 1080p，降低 CPU 与 USB 带宽压力
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        except Exception:
            pass
        return cap

    @staticmethod
    def _annotate(frame, x, y, w, h, size_pct, state):
        """在帧上画人脸框。注意：cv2.putText 不支持中文，
        所以画面叠加文字只用 ASCII，中文都放在 Tkinter 控件里显示。"""
        color = (80, 80, 255) if state == "alert" else \
                (80, 170, 255) if state in ("near", "cooldown") else (120, 220, 120)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(frame, "face %.0f%%" % (size_pct * 100),
                    (x, max(18, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # ---------- 主循环 ----------

    def run(self):
        cap = None
        try:
            if self._load_model() is None:
                return
            cap = self._open_camera()
            if cap is None:
                return

            engine = ProximityEngine()
            start_ts = time.time()
            fail_cnt = 0
            fps, t_last = 0.0, time.time()

            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    # 偶发丢帧先容忍（USB 抖动常见），连续失败才报错退出
                    fail_cnt += 1
                    if fail_cnt > self.MAX_READ_FAIL:
                        self._fatal("摄像头画面读取失败（可能被拔出或被其他程序抢占），已自动停止。")
                        return
                    time.sleep(0.03)
                    continue
                fail_cnt = 0

                # 实时获取滑块参数（阈值 / 灵敏度对应连续帧数 / 冷却秒数）
                p = self.get_params()

                # ---------- 1) 人脸检测：缩到小图提速 ----------
                h, w = frame.shape[:2]
                scale = self.DETECT_WIDTH / float(w)
                small = cv2.resize(frame, (self.DETECT_WIDTH, max(1, int(h * scale))),
                                   interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)          # 直方图均衡，提升暗光检出率
                faces = self.detector.detectMultiScale(
                    gray,
                    scaleFactor=1.1,    # 图像金字塔步长：越小越准越慢
                    minNeighbors=5,     # 越大误检越少但可能漏检，5 是常用均衡值
                    minSize=(40, 40),   # 小图上小于 40px 的人脸直接忽略
                )

                # ---------- 2) 取最大的人脸 → 靠近判定 ----------
                state, size_pct, closeness = "noface", 0.0, 0.0
                if len(faces) > 0:
                    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])   # 最大脸
                    # 小图坐标映射回原始帧坐标
                    x, y, fw, fh = int(x / scale), int(y / scale), int(fw / scale), int(fh / scale)
                    size_pct = fw / float(w)
                    if size_pct >= self.MIN_FACE_RATIO:
                        warmup_ok = (time.time() - start_ts) >= self.WARMUP_SEC
                        st, in_cd = engine.update(
                            size_pct, p["threshold"], p["confirm_frames"],
                            p["cooldown_sec"], allow_fire=warmup_ok)
                        closeness = engine.closeness()
                        if st == "fire":
                            # 触发报警！投递事件给 UI 线程去弹窗/悬浮/响铃
                            self.events.put(("alert", {
                                "popup": random.choice(POPUP_TEXTS),
                                "float": random.choice(FLOAT_TEXTS),
                            }))
                            state = "alert"
                        else:
                            state = "cooldown" if in_cd else st
                    else:
                        engine.miss()      # 太远：不参与判定
                        state = "far"
                    self._annotate(frame, x, y, fw, fh, size_pct, state)
                else:
                    engine.miss()          # 没人脸：绝不触发提醒，计数清零

                # ---------- 3) 帧率统计（平滑显示） ----------
                now = time.time()
                inst = 1.0 / max(now - t_last, 1e-6)
                t_last = now
                fps = inst if fps == 0 else fps * 0.9 + inst * 0.1

                # ---------- 4) 结果写入共享区（加锁） ----------
                with self.shared["lock"]:
                    self.shared["frame"] = frame        # 已画框的帧
                    self.shared["metrics"] = {
                        "state": state, "size_pct": size_pct, "closeness": closeness,
                        "threshold": p["threshold"], "fps": fps, "w": w, "h": h,
                    }
                time.sleep(0.005)   # 轻微让出 CPU（摄像头 30fps 足够）

        except Exception:
            detail = traceback.format_exc()
            log_error(detail)
            self._fatal("程序内部出现异常，已停止：\n%s\n\n详细日志见 face_guard_error.log"
                        % detail[-600:])
        finally:
            if cap is not None:
                cap.release()
            self.events.put(("stopped", None))   # 无论何种退出都通知 UI 复位按钮


# ================================ 主界面 ================================

class FaceGuardApp:

    CANVAS_W, CANVAS_H = 600, 450   # 摄像头画面显示区域
    TICK_MS = 33                    # UI 刷新周期 ≈ 30FPS

    def __init__(self, root):
        self.root = root
        root.title("%s · 护眼距离提醒 %s ｜ 全程离线 · 画面不上传" % (APP_NAME, APP_VERSION))
        root.configure(bg="#fff5f8")
        root.minsize(680, 800)

        # ---- 线程间共享数据 ----
        self.shared = {"lock": threading.Lock(), "frame": None, "metrics": {}}
        self.events = queue.Queue()
        self.worker = None
        self._running = False
        self._ui_ready = False
        # worker 线程读取的参数快照（主线程 _tick 里从滑块同步过来）
        self._params = {"threshold": 1.25, "confirm_frames": 7, "cooldown_sec": 30}
        self._param_lock = threading.Lock()

        # ---- 弹窗/悬浮窗句柄 ----
        self._popup = None
        self._popup_after = None
        self._float = None
        self._float_after = None
        self._photo = None
        self._img_item = None
        self._ph_item = None

        self._build_ui()
        self._ui_ready = True
        self._sync_params()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(self.TICK_MS, self._tick)

    # ---------------- 界面搭建 ----------------

    def _build_ui(self):
        R = self.root
        BG = "#fff5f8"

        # 标题栏
        head = tk.Frame(R, bg=BG)
        head.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(head, text="FaceGuard 酱", font=FONT_TITLE, bg=BG, fg="#e64980").pack(side="left")
        tk.Label(head, text="  二次元护眼距离小卫士 · 离线运行 · 画面绝不离开你的电脑",
                 font=FONT_SMALL, bg=BG, fg="#868e96").pack(side="left", pady=(6, 0))

        # 摄像头画面
        self.canvas = tk.Canvas(R, width=self.CANVAS_W, height=self.CANVAS_H,
                                bg="#3b3a4a", highlightthickness=1,
                                highlightbackground="#ffd9e4")
        self.canvas.pack(padx=14, pady=6)
        self._ph_item = self.canvas.create_text(
            self.CANVAS_W // 2, self.CANVAS_H // 2,
            text="摄像头未启动\n点击下方【▶ 启动摄像头】开始守护你的眼睛 (ฅ'ω'ฅ)",
            fill="#b8b5c4", font=FONT_UI, justify="center")

        # 状态栏 + 靠近程度进度条
        self.status_var = tk.StringVar()
        self.lbl_status = tk.Label(R, textvariable=self.status_var, font=FONT_UI,
                                   bg=BG, fg="#495057", wraplength=640, justify="left")
        self.lbl_status.pack(fill="x", padx=16)
        bar_row = tk.Frame(R, bg=BG)
        bar_row.pack(fill="x", padx=16, pady=(2, 0))
        tk.Label(bar_row, text="靠近程度", font=FONT_SMALL, bg=BG, fg="#868e96").pack(side="left")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("pink.Horizontal.TProgressbar", troughcolor="#ffe3ec",
                        background="#ff8fab", thickness=10)
        self.progress = ttk.Progressbar(bar_row, maximum=100, mode="determinate",
                                        style="pink.Horizontal.TProgressbar")
        self.progress.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # 滑块参数区
        box = tk.LabelFrame(R, text=" ⚙ 参数调节 ", font=FONT_UI, bg=BG,
                            fg="#d6336c", padx=10, pady=6)
        box.pack(fill="x", padx=14, pady=8)

        def add_scale(row, text, from_, to, res, init, fmt):
            tk.Label(box, text=text, font=FONT_UI, bg=BG, fg="#495057") \
                .grid(row=row, column=0, sticky="w", pady=2)
            s = tk.Scale(box, from_=from_, to=to, resolution=res, orient="horizontal",
                         length=280, showvalue=False, bg=BG, highlightthickness=0,
                         troughcolor="#ffd9e4", fg="#d6336c",
                         activebackground="#ff8fab", sliderrelief="flat", bd=0)
            s.grid(row=row, column=1, pady=2)
            val = tk.Label(box, text="", font=FONT_UI, bg=BG, fg="#d6336c",
                           width=10, anchor="w")
            val.grid(row=row, column=2, sticky="w")

            def _upd(v):
                val.configure(text=fmt(float(v)))
                if self._ui_ready:
                    self._sync_params()

            s.configure(command=_upd)
            s.set(init)     # set 会触发 command，自动刷新右侧数值
            return s

        self.sc_threshold = add_scale(0, "靠近触发阈值", 1.05, 1.60, 0.01, 1.25,
                                      lambda v: "%.2f 倍" % v)
        self.sc_sens = add_scale(1, "触发灵敏度", 1, 10, 1, 5,
                                 lambda v: "%d 级" % int(v))
        self.sc_cooldown = add_scale(2, "报警冷却秒数", 5, 120, 1, 30,
                                     lambda v: "%d 秒" % int(v))
        tk.Label(box, text="阈值 = 人脸相对『正常坐姿基线』放大多少倍才触发；"
                           "灵敏度 = 越高要求连续确认的帧数越少（响应越快也越容易误报）；"
                           "冷却 = 两次报警的最小间隔，防止疯狂连报",
                 font=FONT_SMALL, bg=BG, fg="#adb5bd", wraplength=620,
                 justify="left").grid(row=3, column=0, columnspan=3, sticky="w")

        # 开关区
        opt = tk.Frame(R, bg=BG)
        opt.pack(fill="x", padx=18)
        self.var_popup = tk.BooleanVar(value=True)
        self.var_float = tk.BooleanVar(value=True)
        self.var_sound = tk.BooleanVar(value=True)
        self.var_camidx = tk.IntVar(value=0)
        for text, var in (("弹窗提醒", self.var_popup),
                          ("角落悬浮字幕", self.var_float),
                          ("提示音", self.var_sound)):
            tk.Checkbutton(opt, text=text, variable=var, font=FONT_UI, bg=BG,
                           fg="#495057", activebackground=BG).pack(side="left", padx=(0, 14))
        tk.Label(opt, text="设备编号", font=FONT_UI, bg=BG, fg="#495057").pack(side="left")
        ttk.Spinbox(opt, from_=0, to=5, increment=1, width=4, textvariable=self.var_camidx,
                    font=FONT_UI).pack(side="left", padx=(6, 0))

        # 按钮区
        btns = tk.Frame(R, bg=BG)
        btns.pack(pady=10)
        self.btn_start = tk.Button(btns, text="▶ 启动摄像头", font=FONT_BTN, bg="#ff8fab",
                                   fg="white", activebackground="#ff6b9d",
                                   activeforeground="white", relief="flat", padx=24,
                                   pady=6, cursor="hand2", command=self.start_cam)
        self.btn_start.pack(side="left", padx=8)
        self.btn_stop = tk.Button(btns, text="■ 停止摄像头", font=FONT_BTN, bg="#ffd9e4",
                                  fg="#b2506e", activebackground="#ffc2d4",
                                  activeforeground="#b2506e", relief="flat", padx=24,
                                  pady=6, cursor="hand2", state="disabled",
                                  command=self.stop_cam)
        self.btn_stop.pack(side="left", padx=8)

        # 底部隐私声明
        tk.Label(R, text="※ 本程序 100% 离线：无网络请求、无遥测、模型内置；"
                         "画面仅在内存中实时处理，关闭即消失。",
                 font=FONT_SMALL, bg=BG, fg="#adb5bd").pack(side="bottom", pady=(0, 8))

        self.status_var.set("状态：待机中～ 点击【▶ 启动摄像头】开始守护 (ฅ'ω'ฅ)")

    # ---------------- 参数同步（主线程写，worker 读） ----------------

    def _sync_params(self):
        sens = int(float(self.sc_sens.get()))
        with self._param_lock:
            self._params["threshold"] = float(self.sc_threshold.get())
            # 灵敏度 1~10 → 需要连续确认的帧数 11~2（灵敏度越高确认越少）
            self._params["confirm_frames"] = max(2, 12 - sens)
            self._params["cooldown_sec"] = int(float(self.sc_cooldown.get()))

    def get_params(self):
        """worker 线程调用：拿一份参数快照。"""
        with self._param_lock:
            return dict(self._params)

    # ---------------- 启动 / 停止 ----------------

    def start_cam(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            cam_idx = int(self.var_camidx.get())
        except Exception:
            cam_idx = 0
        with self.shared["lock"]:          # 清掉上一轮残留画面
            self.shared["frame"] = None
            self.shared["metrics"] = {}
        self.worker = CameraWorker(cam_idx, self.shared, self.events, self.get_params)
        self.worker.start()
        self._running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

    def stop_cam(self):
        if self.worker:
            self.worker.stop()             # 不阻塞 UI，等 'stopped' 事件复位按钮

    def _set_stopped_ui(self):
        self._running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        with self.shared["lock"]:
            self.shared["frame"] = None
            self.shared["metrics"] = {}
        self._show_placeholder(True)

    # ---------------- UI 心跳 ----------------

    def _tick(self):
        # 1) 同步滑块 → worker 可读快照
        self._sync_params()
        # 2) 处理 worker 投递的事件
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "alert":
                    self._on_alert(payload)
                elif kind == "fatal":
                    self._set_stopped_ui()
                    messagebox.showerror(APP_NAME, payload)
                elif kind == "stopped":
                    self._set_stopped_ui()
        except queue.Empty:
            pass
        # 3) 画面刷新：最小化时跳过绘制省 CPU，但后台检测线程照常运行
        if self.root.state() != "iconic":
            self._draw_frame()
        self._update_status()
        # 4) 下一拍
        self.root.after(self.TICK_MS, self._tick)

    def _draw_frame(self):
        with self.shared["lock"]:
            frame = self.shared["frame"]
        if frame is None:
            self._show_placeholder(True)
            return
        self._show_placeholder(False)
        h, w = frame.shape[:2]
        scale = min(self.CANVAS_W / float(w), self.CANVAS_H / float(h))
        if scale < 1.0:
            frame = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))),
                               interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))   # 保留引用防 GC
        if self._img_item is None:
            self._img_item = self.canvas.create_image(
                self.CANVAS_W // 2, self.CANVAS_H // 2, image=self._photo)
        else:
            self.canvas.itemconfig(self._img_item, image=self._photo)

    def _show_placeholder(self, show):
        if self._ph_item is not None:
            self.canvas.itemconfig(self._ph_item, state="normal" if show else "hidden")
        if self._img_item is not None:
            self.canvas.itemconfig(self._img_item, state="hidden" if show else "normal")

    def _update_status(self):
        with self.shared["lock"]:
            m = dict(self.shared["metrics"])
        if not m:
            if not self._running:
                self.progress["value"] = 0
            return
        state = m.get("state", "noface")
        txt, color = STATE_TEXT.get(state, ("……", "#495057"))
        if state in ("noface", "far"):
            extra = ""
        else:
            extra = " ｜ 人脸宽度 %.0f%% ｜ 距离水平 %.0f%%（触发线 %.0f%%）" % (
                m["size_pct"] * 100, m["closeness"] * 100, m["threshold"] * 100)
        self.status_var.set("状态：%s%s ｜ %.1f FPS ｜ %dx%d" % (
            txt, extra, m.get("fps", 0.0), m.get("w", 0), m.get("h", 0)))
        self.lbl_status.configure(fg=color)
        closeness = m.get("closeness", 0.0)
        threshold = max(m.get("threshold", 1.25), 1e-6)
        self.progress["value"] = max(0.0, min(100.0, closeness / threshold * 100.0))

    # ---------------- 提醒：弹窗 / 悬浮字幕 / 提示音 ----------------

    def _on_alert(self, payload):
        kaomoji, body = payload["popup"]
        if self.var_popup.get():
            self._show_popup(kaomoji, body)
        if self.var_float.get():
            self._show_float(payload["float"])
        self._play_sound()

    def _show_popup(self, kaomoji, body):
        """二次元弹窗（非模态，自动 9 秒关闭；重复报警时复用同一个窗口刷新文案）。
        注意：故意不用 messagebox（模态会卡住主循环），也不用 transient
        （transient 窗口会随主窗口最小化而隐藏，违背"最小化仍要提醒"）。"""
        if self._popup is not None and self._popup.winfo_exists():
            pop = self._popup
        else:
            pop = tk.Toplevel(self.root)
            pop.title("%s · 护眼提醒" % APP_NAME)
            pop.configure(bg="#ffeef2")
            pop.resizable(False, False)
            pop.attributes("-topmost", True)     # 置顶，玩游戏/写代码也看得见
            inner = tk.Frame(pop, bg="#ffeef2", padx=26, pady=18)
            inner.pack()
            lbl_title = tk.Label(inner, text="", font=FONT_POP, fg="#e64980", bg="#ffeef2")
            lbl_title.pack()
            lbl_body = tk.Label(inner, text="", font=FONT_UI, fg="#8a4b60",
                                bg="#ffeef2", justify="left")
            lbl_body.pack(pady=(8, 12))
            tk.Button(inner, text="知道啦～(๑•̀ㅂ•́)و✧", font=FONT_BTN, bg="#ff8fab",
                      fg="white", activebackground="#ff6b9d", activeforeground="white",
                      relief="flat", padx=16, pady=4, cursor="hand2",
                      command=pop.destroy).pack()
            self._popup = pop
            self._popup_labels = (lbl_title, lbl_body)
        lbl_title, lbl_body = self._popup_labels
        lbl_title.configure(text=kaomoji)
        lbl_body.configure(text=body)
        pop.update_idletasks()
        sw = pop.winfo_screenwidth()
        pop.geometry("+%d+140" % max(0, int((sw - pop.winfo_reqwidth()) / 2)))
        if self._popup_after is not None:
            try:
                self.root.after_cancel(self._popup_after)
            except Exception:
                pass
        self._popup_after = self.root.after(9000, self._close_popup)

    def _close_popup(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup_after = None

    def _show_float(self, text):
        """屏幕右上角悬浮字幕：无边框、置顶，6 秒后自动消失。"""
        if self._float is not None and self._float.winfo_exists():
            f = self._float
        else:
            f = tk.Toplevel(self.root)
            f.overrideredirect(True)             # 无边框
            f.attributes("-topmost", True)
            self._float_lbl = tk.Label(f, text="", font=(_FONT, 13, "bold"),
                                       fg="white", bg="#ff6b9d", padx=20, pady=10)
            self._float_lbl.pack()
            self._float = f
        self._float_lbl.configure(text=text)
        f.update_idletasks()
        x = f.winfo_screenwidth() - f.winfo_reqwidth() - 24
        f.geometry("+%d+90" % max(0, int(x)))
        if self._float_after is not None:
            try:
                self.root.after_cancel(self._float_after)
            except Exception:
                pass
        self._float_after = self.root.after(6000, self._hide_float)

    def _hide_float(self):
        if self._float is not None and self._float.winfo_exists():
            self._float.destroy()
        self._float_after = None

    def _play_sound(self):
        """两声下行提示音。放在子线程：winsound.Beep 是阻塞调用，别卡 UI。"""
        if not self.var_sound.get() or winsound is None:
            return

        def _beep():
            try:
                winsound.Beep(1046, 150)   # 哆～
                time.sleep(0.03)
                winsound.Beep(784, 280)    # 咦～（下行两音 = "注意"）
            except Exception:
                pass

        threading.Thread(target=_beep, daemon=True).start()

    # ---------------- 退出清理 ----------------

    def _on_close(self):
        try:
            if self.worker and self.worker.is_alive():
                self.worker.stop()
                self.worker.join(timeout=2.0)
        finally:
            self.root.destroy()


# ================================ 入口 ================================

def main():
    # 打包脚本会调用：python face_guard.py --cascade-path
    # → 打印 Haar 模型的绝对路径后退出，build.bat 用它来拼 --add-data 参数
    if "--cascade-path" in sys.argv:
        path = find_cascade_path()
        if path:
            print(path)
            return
        print("CASCADE_NOT_FOUND", file=sys.stderr)
        sys.exit(1)

    try:
        root = tk.Tk()
        FaceGuardApp(root)
        root.mainloop()
    except Exception:
        detail = traceback.format_exc()
        log_error(detail)
        try:
            messagebox.showerror(APP_NAME, "启动失败：\n%s\n\n详细日志见同目录 face_guard_error.log"
                                 % detail[-500:])
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
