# Windows 构建

## GitHub Actions

工作流文件：.github/workflows/windows-build.yml

触发条件：
- 推送到 main 或 feature/** 分支
- 针对 main 创建或更新 Pull Request
- 在 Actions 页面手动运行 workflow_dispatch

工作流先在 Windows runner 上运行 pytest。测试成功后，使用 PyInstaller 在 Windows runner 上生成 onedir 应用目录，再压缩并上传 Actions Artifact。

## 下载

1. 打开 GitHub 仓库的 Actions 页面。
2. 选择最新一次成功的 Windows build。
3. 在 Artifacts 区域下载 LightningCAD-AI-Windows-x64。
4. 解压后运行 LightningCAD-AI/LightningCAD-AI.exe。

## 为什么先采用 onedir

OCR 模型、ONNX Runtime 和 OpenCV 都包含额外的数据文件或原生动态库。onedir 便于检查这些资源是否被正确收集，也更容易排查 Windows 启动问题。待实机验证稳定后，再尝试单文件 EXE。

## 本地构建

在 Windows 10/11、Python 3.12 环境：

    python -m pip install -e ".[dev]"
    pyinstaller --noconfirm --clean --windowed --onedir --name LightningCAD-AI --collect-all rapidocr --collect-all onnxruntime --collect-all cv2 --collect-all shapely --collect-all pyclipper --collect-all omegaconf --add-data "config;config" run.py

输出目录：dist/LightningCAD-AI/
