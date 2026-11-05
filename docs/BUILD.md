# Windows 单文件 EXE 构建

## GitHub Actions

工作流文件：.github/workflows/windows-build.yml

触发条件：
- 推送到 main 或 feature/** 分支
- 针对 main 创建或更新 Pull Request
- 在 Actions 页面手动运行 workflow_dispatch

工作流先在 Windows runner 上运行 pytest。测试成功后，使用 PyInstaller 的 `--onefile` 模式将程序、OCR 模型、OpenCV 和 ONNX Runtime 依赖打包为一个 Windows x64 EXE。OpenCADStudio v2026.44 是独立安装的 CAD 引擎，不打包进 LightningCAD EXE。

## 下载与运行

1. 打开 GitHub 仓库的 Actions 页面。
2. 选择最新一次成功的 Windows build。
3. 下载名为 `LightningCAD-AI-EXE-Windows-x64` 的构建产物。
4. 解压 Artifact ZIP，文件夹中只有 `LightningCAD-AI.exe`。
5. 双击 `LightningCAD-AI.exe` 运行。无需安装 Python，也无需另外复制依赖文件夹；首次使用 CAD 绘图前需安装 OpenCADStudio v2026.44，并在软件设置栏指定其 EXE 路径（如未自动识别）。

注意：GitHub Actions 的 Artifact 下载机制会将上传文件包装为 ZIP；ZIP 内部只包含最终 EXE，不是 onedir 程序目录。单文件程序启动时会先将依赖释放到 Windows 临时目录，因此首次启动可能稍慢。

## 本地构建

在 Windows 10/11、Python 3.12 环境：

    python -m pip install -e ".[dev]"
    pyinstaller --noconfirm --clean --windowed --onefile --name LightningCAD-AI --collect-all rapidocr --collect-all onnxruntime --collect-all cv2 --collect-all shapely --collect-all pyclipper --collect-all omegaconf --add-data "config;config" run.py

输出文件：`dist/LightningCAD-AI.exe`
