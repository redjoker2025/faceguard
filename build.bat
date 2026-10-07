@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==================================================
echo   FaceGuard 酱 - PyInstaller 单文件 EXE 打包脚本
echo ==================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 python 命令。请先安装 Python 64 位并勾选 "Add Python to PATH"。
    pause
    exit /b 1
)

echo [1/3] 安装/检查依赖 ^(requirements.txt^)...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络或 pip 源。
    pause
    exit /b 1
)

echo.
echo [2/3] 定位内置人脸模型...
set "CASCADE="
for /f "usebackq delims=" %%i in (`python face_guard.py --cascade-path`) do set "CASCADE=%%i"
if not defined CASCADE (
    echo [错误] 没有找到 haarcascade_frontalface_default.xml 人脸模型。
    echo        请确认 opencv-python-headless 已正确安装，或手动指定 --add-data。
    pause
    exit /b 1
)
echo        模型路径: %CASCADE%

echo.
echo [3/3] 开始打包（第一次大约 1~3 分钟，请耐心等待）...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "FaceGuard" --add-data "%CASCADE%;." face_guard.py
if errorlevel 1 (
    echo [错误] 打包失败，请把上面的完整报错信息反馈排查。
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   打包完成！输出文件: dist\FaceGuard.exe
echo   双击即可运行，无需安装 Python，全程离线。
echo.
echo   提示：
echo   - 首次启动要解压运行时，慢几秒属正常现象。
echo   - 若杀毒软件/SmartScreen 报警，属未签名单文件 EXE 常见误报，
echo     加入白名单或点击"仍要运行"即可。
echo ==================================================
pause
