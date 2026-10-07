# FaceGuard 酱 · 鲸鱼娘 —— 成品下载

本分支只放**打包好的成品**，源码、文档与构建脚本都在 [`main` 分支](https://github.com/redjoker2025/faceguard)。

## 最新版本：v2.1（立绘版）

| 项目 | 内容 |
|---|---|
| 文件 | `FaceGuard.exe` |
| 大小 | 70,900,559 字节（67.6 MiB） |
| SHA256 | `D92100A784AC81CB8CE53C82A026FD5DAF1AA0E42B4477C671F209A2C0D6DAC1` |
| 运行环境 | Windows 10 / 11（64 位），无需安装 Python |
| 构建环境 | Windows 11 64 位 · Python 3.14.5 · PyInstaller 6.17.0 |
| 打包命令 | `python -m PyInstaller --noconfirm --clean FaceGuard.spec` |
| 已内嵌 | 人脸模型 `haarcascade_frontalface_default.xml` + `assets/` 两张鲸鱼娘立绘 |

直链下载：<https://raw.githubusercontent.com/redjoker2025/faceguard/releases/FaceGuard.exe>

## 怎么用

1. 下载 `FaceGuard.exe`，双击运行（单文件，免安装）；
2. 首次启动会先解压到 `%TEMP%\_MEIxxxxx`，慢几秒属正常；
3. 点 **▶ 启动摄像头**，保持正常坐姿约 2 秒让程序学习基线，之后凑近屏幕就会提醒；
4. 最小化窗口后，右下角会出现鲸鱼娘悬浮球，光环颜色随距离由蓝渐变到红
   （蓝 = 远，红 = 贴脸），可拖动、悬停看数值、双击回主窗口、右键菜单退出。

> Windows SmartScreen / 杀软提示：未签名的 PyInstaller 单文件 EXE 被误报是常态，
> 点「更多信息 → 仍要运行」或加入白名单即可。

## 校验下载完整性

```powershell
Get-FileHash .\FaceGuard.exe -Algorithm SHA256
# 期望：D92100A784AC81CB8CE53C82A026FD5DAF1AA0E42B4477C671F209A2C0D6DAC1
```

也可以直接用 `SHA256SUMS.txt`：

```powershell
certutil -hashfile FaceGuard.exe SHA256
```

## 这一版有什么

- **v2.1**：鲸鱼娘换成抠图得到的**真立绘**；悬浮球改成「圆形头像 + 距离色光环」；
  立绘缺失/损坏时自动退回 Canvas 矢量画法，界面不会开天窗。
- **v2.0**：整个界面换肤成**深海蓝渐变**主题；新增**最小化悬浮球**（由蓝到红表示远近）；
  界面文案鲸鱼娘化。
- **v1.0**：首个版本——摄像头 + Haar 人脸检测 + 靠近判定 + 弹窗/悬浮字幕/提示音，粉色主题。

## 隐私

- 程序内**没有任何网络请求**：不下载、不上传、不含遥测；
- 人脸模型与立绘都随 EXE 内置，运行时不需要联网；
- 摄像头画面只在内存中处理，关闭即释放，不写任何文件（只在崩溃时写同目录 `face_guard_error.log`）。
