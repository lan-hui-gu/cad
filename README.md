# LightningCAD-AI

防雷检测手绘草图识别与 DXF 工程图辅助生成工具。项目以开源计算机视觉、OCR 和 DXF 库为基础，面向俯视拍摄的防雷检测手绘平面草图。

## 项目目标

将现场俯视照片转换为可校核的矢量候选图，减少重复描图工作。程序输出 DXF、识别叠加预览图和 JSON 识别数据。

重要：本项目是检测制图辅助工具，不替代现场测量、检测人员判断、设计复核或规范符合性审查。未经人工校核的 DXF 不得作为正式检测成果。

## 开源技术栈

| 模块 | 开源项目 | 用途 |
|---|---|---|
| 图像处理 | OpenCV | 二值化、边缘检测、直线和轮廓提取 |
| OCR | RapidOCR + ONNX Runtime | 中文、数字、尺寸文本候选识别，CPU 推理 |
| 几何 | NumPy + 自研约束算法 | 直线正交候选、圆弧拟合、交点分析 |
| CAD | ezdxf | 生成带分层的 DXF 文件 |
| 桌面界面 | Python Tkinter | 本地图片导入、预览、校核和导出 |
| Windows 打包 | PyInstaller | 生成 Windows 可运行程序 |
| CI/CD | GitHub Actions | 自动测试、Windows 编译、上传构建产物 |

所有图像识别在本地执行，不上传现场照片，不需要云端 AI API，也不要求 NVIDIA GPU。

## 已固化的图纸语义规则

1. 黑色实心三角形及邻近字母/数字：测点候选，三角形中心为点位基准。
2. 带箭头或弯钩的细线：说明引线候选；不能与图例中的引下线符号混为一类。
3. 尺寸线、尺寸界线及距离文字：尺寸标注候选，不是建筑线路。
4. 连续且构成建筑平面边界的手绘线：建筑结构候选。
5. 带 X 标记的线可能是建筑结构线，也可能是明装接闪带，不能只凭 X 标记决定类别。
6. 近水平/垂直直线优先采用正交约束；明显弧线保留为圆弧/自由曲线候选。
7. 标高符号和标高数值独立识别，不归入测点。

规则配置位于 config/recognition_rules.json。

## Windows 本地运行

建议 Windows 10/11 x64、Python 3.12、16 GB RAM。无 NVIDIA GPU 也可以运行。

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python run.py

如果 PowerShell 不允许执行激活脚本，可以直接使用：

    .venv\Scripts\python.exe -m pip install -e ".[dev]"
    .venv\Scripts\python.exe run.py

首次运行 OCR 时，RapidOCR 会初始化本地模型。建议使用 ONNX Runtime CPU。

## 使用流程

1. 使用手机俯视拍摄草图，尽量保持纸面平整、镜头与纸面平行、四周完整入镜、光线均匀。
2. 打开程序并导入 JPG/PNG/BMP/TIFF。
3. 选择照片旋转角度，按需启用 OCR。
4. 点击“开始识别”，查看原图叠加识别结果。
5. 在右侧候选列表中检查线条、符号和文字；对不确定类别进行人工修改。
6. 如有已知长度，输入比例标定值（mm/px）。没有可靠标定时，导出的 DXF 保留像素坐标，不伪造实际尺寸。
7. 导出 DXF、JSON 和识别预览图。
8. 使用 LibreCAD、QCAD 或其他兼容 DXF 的 CAD 软件打开 DXF，完成最终复核。

## 输出图层

- BUILDING_REVIEW：建筑结构候选
- STRIP_REVIEW：结构线/明装接闪带待判别线
- DIMENSION_REVIEW：尺寸标注候选
- LEADER_REVIEW：说明引线候选
- TEST_POINT_REVIEW：测点候选
- ROUND_SYMBOL_REVIEW：圆形符号候选
- CURVE_REVIEW：弧线/自由曲线候选
- OCR_TEXT：OCR 文字
- REVIEW_NOTE：人工复核提示

## 开发与测试

    python -m pip install -e ".[dev]"
    pytest -q

## GitHub 自动编译

推送到 main 或 feature/** 分支、创建 PR，或手动触发 Actions，都会运行 Windows 测试和打包任务。

工作流采用 PyInstaller `--onefile`，最终产物为单个 `LightningCAD-AI.exe`。无需安装 Python，也无需单独保留依赖文件夹。GitHub Actions Artifact 下载后解压，文件夹中只有该 EXE。

首次启动时，单文件程序会将内部依赖释放到 Windows 临时目录；启动速度可能比 onedir 稍慢。OCR 模型与原生运行库均随 EXE 一起打包。

## 识别能力边界

- 线条和轮廓检测采用 OpenCV 传统视觉算法；手绘重叠、阴影、折痕和笔迹断裂会影响识别。
- OCR 结果只是文字候选，手写尺寸中的小数点、单位和数字必须核对。
- 结构线与明装接闪带存在语义重叠，程序保留待复核类别，不会擅自定性。
- 没有标定信息时，DXF 坐标不是毫米，不得当作实测尺寸。
- 当前版本不自动判定防雷系统是否符合规范，也不自动推断电气连接可靠性。

## 许可证

本仓库自研代码采用 MIT License。第三方依赖保持各自上游许可证，详见 THIRD_PARTY_NOTICES.md。
