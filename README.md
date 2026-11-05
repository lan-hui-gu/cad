# LightningCAD-AI

防雷检测手绘草图识别与 CAD 工程图辅助生成工具。项目以开源计算机视觉、OCR 和 OpenCADStudio v2026.44 原生自动化接口为基础，面向俯视拍摄的防雷检测手绘平面草图。

## 项目目标

将现场俯视照片转换为可校核的矢量候选图，减少重复描图工作。程序通过 OpenCADStudio 原生 CAD 数据库输出 DWG（默认）或 DXF，并保留识别叠加预览图和 JSON 识别数据。

重要：本项目是检测制图辅助工具，不替代现场测量、检测人员判断、设计复核或规范符合性审查。未经人工校核的 DXF 不得作为正式检测成果。

## 开源技术栈

| 模块 | 开源项目 | 用途 |
|---|---|---|
| 图像处理 | OpenCV | 二值化、边缘检测、直线和轮廓提取 |
| OCR | RapidOCR + ONNX Runtime | 中文、数字、尺寸文本候选识别，CPU 推理 |
| 几何 | NumPy + 自研约束算法 | 直线正交候选、圆弧拟合、交点分析 |
| CAD | OpenCADStudio v2026.44 原生自动化 API | 创建、审核并保存 DWG/DXF 实体 |
| 桌面界面 | Python Tkinter | 本地图片导入、预览、校核和导出 |
| Windows 打包 | PyInstaller | 生成 Windows 可运行程序 |
| CI/CD | GitHub Actions | 自动测试、Windows 编译、上传构建产物 |

所有图像识别在本地执行，不上传现场照片，不需要云端 AI API，也不要求 NVIDIA GPU。OpenCADStudio v2026.44 需单独安装；LightningCAD 通过其官方本地自动化 API 调用原生 CAD 数据库，不内置 LibCAD 或第二套 CAD 写入引擎。

## 已固化的图纸语义规则

1. 黑色实心三角形及邻近字母/数字：测点候选，三角形中心为点位基准。
2. 带箭头或弯钩的细线：说明引线候选；不能与图例中的引下线符号混为一类。
3. 尺寸线、尺寸界线及距离文字：尺寸标注候选，不是建筑线路。
4. 连续且构成建筑平面边界的手绘线：建筑结构候选。
5. 带 X 标记的线可能是建筑结构线，也可能是明装接闪带，不能只凭 X 标记决定类别。
6. 近水平/垂直直线优先采用正交约束；明显弧线保留为圆弧/自由曲线候选。
7. 标高符号和标高数值独立识别，不归入测点。

规则配置位于 config/recognition_rules.json。

## OpenCADStudio CAD 引擎要求

- Windows 电脑需单独安装 OpenCADStudio **v2026.44**。
- LightningCAD 启动后会检测 `OpenCADStudio.exe`；若未自动找到，可在设置栏手动指定路径。
- 绘图时由 LightningCAD 启动 OpenCADStudio 的本地 HTTP 自动化服务，调用原生实体创建与保存校验接口；服务仅绑定 `127.0.0.1`，使用随机本地令牌。
- 默认输出 DWG 2018；也可选择 DXF 2000。没有比例标定时使用图像像素单位，不代表现场实测尺寸。

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
2. 导入 JPG/PNG/BMP/TIFF，设置旋转角度，按需启用本地 OCR。
3. 点击“1.识别原始线条”，程序只提取原始线段和弧线候选，不直接生成 CAD。
4. 点击“2.简化线条”，执行共线合并、重复消减、短间断合并和有限正交约束。
5. 在图上或右侧列表选择简化线段，标记为建筑结构、明装/暗装接闪带、引下线、说明引线或尺寸线；曲线在弧线候选列表中单独标记。
6. 选择点位类别后启用“在图上添加点位”，在照片上点击测点、接闪杆、标高等位置并录入编号。
7. 双击 OCR 文字进行校正并确认。未确认文字不会进入 CAD。
8. 点击“3.完成标记”。只有人工确认的图元才会进入最终绘图模型。
9. 输入可靠比例后，点击“4.OpenCADStudio 原生绘图”。LightningCAD 通过 OpenCADStudio v2026.44 的本地 HTTP 自动化 API 创建原生 CAD 实体，执行保存校验并输出 DWG（默认）或 DXF。
10. 程序会按设置自动在 OpenCADStudio 中打开成果图；也可以在 OpenCADStudio 中继续编辑图层、线段、文字和符号。

未标记图元不会输出。没有可靠比例标定时，DXF 坐标为像素单位，不代表现场实际尺寸。

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
