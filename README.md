# LightningCAD-AI · 防雷检测草图辅助识别

## Windows 单文件 EXE 下载

**[直接下载 LightningCAD-AI.exe（Windows 64 位）](https://github.com/lan-hui-gu/cad/releases/download/v0.2.0-alpha.1/LightningCAD-AI.exe)**

[查看 GitHub Releases 发布页](https://github.com/lan-hui-gu/cad/releases/tag/v0.2.0-alpha.1)

- 版本：v0.2.0-alpha.1（测试版）
- 文件：LightningCAD-AI.exe（约 125.5 MB）
- 下载后双击运行，不需要另外安装 Python，也不需要保留依赖文件夹。
- 已通过 GitHub Actions Windows 构建及自动化测试；真实电脑上的启动和图纸识别精度仍需现场验证。
- 本版为识图候选和 DXF 重绘辅助工具，未核准的尺寸、检测点和线路不得直接用于正式检测报告。

## 源码与开发

开发代码在 [feature/lightningcad-open-source-core](https://github.com/lan-hui-gu/cad/tree/feature/lightningcad-open-source-core) 分支，对应 [PR #1](https://github.com/lan-hui-gu/cad/pull/1)。

项目采用 OpenCV、RapidOCR、ONNX Runtime、ezdxf 和 PyInstaller 等开源组件。
