# FaceGuard 酱 · 二次元护眼距离提醒

读电脑摄像头 → 本地人脸检测 → 发现你**持续凑近屏幕**就弹窗提醒（二次元风格）。
**全程离线**：无任何云端 API、无网络请求、无模型在线下载，画面只在本机内存中处理，绝不保存、绝不上传。

## 交付物清单

| 文件 | 说明 |
|---|---|
| `face_guard.py` | 完整源码（单文件，含详细注释） |
| `requirements.txt` | pip 依赖清单 |
| `build.bat` | 一键打包脚本（自动定位模型 → PyInstaller 单文件 EXE） |
| `README.md` | 本文档：环境 / 打包 / 使用说明 |

---

## ① 运行环境清单

- **系统**：Windows 10 / 11（64 位）
- **Python**：3.9 ~ 3.14（64 位；装的时候勾选 *Add Python to PATH*）
- **pip 安装**（只装这三个，无 GPU 要求、无需联网模型）：

```bat
pip install -r requirements.txt
```

| 包 | 用途 | 备注 |
|---|---|---|
| `opencv-python-headless` | 摄像头读取 + Haar 人脸检测 | 无 GUI 版，体积更小、避开 Qt 插件冲突；换 `opencv-python` 也能跑，两者不要同时装 |
| `pillow` | 把摄像头帧刷进 Tkinter 画布 | 算法不依赖它 |
| `pyinstaller` | 仅打包 EXE 时需要 | 平时运行程序不需要 |

Tkinter 是 Python 标准库，不用装；`numpy` 会随 opencv 自动装上。

## ② 直接运行（开发模式）

```bat
python face_guard.py
```

## ③ 打包成单文件 EXE

### 方法一：一键脚本（推荐）

双击 `build.bat`，它做三件事：装依赖 → 用 `python face_guard.py --cascade-path` 自动定位
opencv 包里的人脸模型 XML → 调 PyInstaller 打包。产物：`dist\FaceGuard.exe`。

### 方法二：手动命令

```bat
:: 1. 先拿到人脸模型在你机器上的绝对路径（程序内置了这个查询入口）
python face_guard.py --cascade-path
:: 假设输出：C:\Python312\Lib\site-packages\cv2\data\haarcascade_frontalface_default.xml

:: 2. 打包（把上面输出的路径填进去）
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FaceGuard ^
  --add-data "C:\Python312\Lib\site-packages\cv2\data\haarcascade_frontalface_default.xml;." ^
  face_guard.py
```

PowerShell 用单行版（`^` 换行符在 PowerShell 里不认）：

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FaceGuard --add-data "<模型路径>;." face_guard.py
```

### 打包注意点（踩坑清单）

1. **模型必须 `--add-data` 进 EXE**，否则打包后 `找不到人脸模型` 报错。程序运行时用
   `sys._MEIPASS`（onefile 的解包目录）找它，这条路已写好，你只要别漏 `--add-data`。
2. **`--add-data` 的分隔符在 Windows 是 `;`**（Linux/macOS 才是 `:`）。
3. **`--windowed`（等价 `--noconsole`）隐藏黑窗**：没有控制台后，崩溃信息会写到
   EXE 同目录的 `face_guard_error.log`——"双击没反应"时先看这个文件。
4. **推荐 `opencv-python-headless`**：比完整版小十几 MB，且避开 cv2 自带 Qt 插件在
   打包后的冲突；若用完整版 `opencv-python` 打包报 Qt/platform 插件错误，改装 headless。
5. **用 pip 装 opencv，别用 conda 的**：conda 版目录布局不同，`cv2.data` 经常缺失。
6. **杀毒软件 / SmartScreen 误报**：未签名的 PyInstaller onefile EXE 被误报是常态。
   加白名单即可；介意的话可给 EXE 签名，或加 `--noupx`（装了 UPX 时 PyInstaller 会自动压缩，
   部分杀软对 UPX 壳更敏感）。
7. **EXE 的位数 = 打包用 Python 的位数**：64 位 Python 打出的 EXE 只能跑在 64 位系统上。
8. **首次启动慢几秒是正常的**：onefile 会先解压到 `%TEMP%\_MEIxxxxx` 再运行。
9. **分发验证**：拿到一台没装 Python 的电脑上双击试一下，确认模型、摄像头都正常。
10. **想再瘦身**：可把 `face_guard.py` 和 build 命令里的模型换成
    `lbpcascade_frontalface.xml`（约 70KB，更快但精度略低），整体积能再省 ~1MB；
    常规 Haar 版 EXE 约 40~55MB 属正常（大头是 OpenCV 本体）。

## ④ 使用说明

1. 双击 `FaceGuard.exe`（或开发模式 `python face_guard.py`），点击 **▶ 启动摄像头**。
2. 画面上会框出你的人脸并显示宽度占比；程序先用约 2 秒学习你当前的坐姿作为**基线**。
3. 当你凑近屏幕、人脸比基线放大到**超过阈值**并**连续多帧**确认后，触发提醒：
   弹窗（自动 9 秒关闭）＋ 屏幕右上角悬浮字幕（6 秒消失）＋ 两声提示音。
4. 报警后进入**冷却期**，冷却内不重复报警；若冷却结束你仍然贴脸，会再提醒一次。
5. 最小化主窗口？没关系，**后台继续检测**，该弹的提醒照常弹出。
6. 退出直接点右上角 ×，摄像头会自动释放。

### 参数怎么调

| 控件 | 含义 | 调参建议 |
|---|---|---|
| 靠近触发阈值 | 人脸相对基线放大多少倍触发（1.05~1.60，默认 1.25） | 误报多 → 调大；太迟才报 → 调小 |
| 触发灵敏度 | 报警前需连续确认的帧数（1~10，默认 5 → 连续 7 帧） | 晃动误报 → 调低；想秒报 → 调高 |
| 报警冷却秒数 | 两次报警最小间隔（5~120 秒，默认 30） | 按需即可 |
| 弹窗 / 悬浮字幕 / 提示音 | 三种提醒方式的开关 | — |
| 设备编号 | 摄像头索引（默认 0 = 自带摄像头） | 外接摄像头打不开时试 1、2 |

### 边界情况处理对照

| 场景 | 程序行为 |
|---|---|
| 摄像头打开失败 / 被占用 / 无权限 | 主线程弹窗说明原因与排查步骤，界面复位可重试 |
| 画面里没有人脸 | 不触发提醒，状态栏提示，连续帧计数清零 |
| 单帧晃动 / 突变 | EMA 平滑 + 连续多帧确认 + 太远(＜8%画面宽)不参与判定，三重过滤防误报 |
| 长时间贴脸不动 | 基线冻结 + 冷却期内不重复报警，冷却结束仍贴近才再提醒 |
| 主窗口最小化 | 检测线程继续运行，弹窗/悬浮窗置顶弹出；最小化时暂停刷帧省 CPU |
| 运行中摄像头被拔出 | 连续读取失败约 1 秒后自动停止并弹窗 |

## 常见问题

- **双击 EXE 没反应**：看同目录 `face_guard_error.log`；九成是杀软拦截或模型没打进去。
- **画面黑屏**：检查 Windows 隐私设置是否允许桌面应用访问相机；或有别的程序占用。
- **从不太报 / 报太勤**：按上面"参数怎么调"调阈值与灵敏度即可，状态栏的"距离水平 vs 触发线"能直观看到差距。

## 隐私说明

本程序不含任何网络代码：不请求、不下载、不上传。人脸检测模型
（`haarcascade_frontalface_default.xml`，OpenCV 官方自带级联）随 EXE 内置。
摄像头帧仅在内存中完成"缩放 → 灰度 → 检测 → 画框"，进程关闭即释放，不落盘。
