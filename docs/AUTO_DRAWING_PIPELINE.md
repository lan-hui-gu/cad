# 自动根据简化图生成 CAD

## 目标流程

1. OpenCV 识别原始照片中的直线、曲线、三角形、圆形符号和 OCR 文字。
2. 先从闭合轮廓候选中确定主图区域，在适度留白范围内筛除远离主图的页眉、页脚和杂散笔迹；再由 simplify_segments 执行共线合并、断点连接和交点拓扑拆分。
3. render_simplified_preview 使用纯白画布绘制简化几何，作为用户看到的简化图。
4. build_automatic_drawing_model 从同一份简化结果建立 CAD 几何模型，不要求逐条标记线段。
5. drawing_model_to_opencad_entities 将模型转换为 OpenCADStudio 原生实体。
6. OpenCADStudio v2026.44 创建实体并保存 DWG/DXF。

## 单一几何来源

简化预览和 CAD 导出共用 result.lines、result.curves、result.triangles、result.colored_markers、result.round_symbols 与 result.texts。CAD 导出不再重新识别原始照片，也不从预览 PNG 反推坐标。

## 图层

- SIMPLIFIED_GEOMETRY：简化直线和线段。
- ARC：简化曲线。
- SIMPLIFIED_SYMBOL：识别出的三角形和圆形符号。
- SIMPLIFIED_TEXT：OCR 文字候选。

## 比例

若 OCR 尺寸文字已与尺寸线建立关联，则估算 mm/px。多组结果冲突时不自动采用，退回像素单位。单一尺寸估算会标记为低置信度。估算比例不能替代现场实测标定。

## 主图区域筛选

- 优先选取面积最大的闭合矩形轮廓作为主图候选，并在四周保留尺寸线和引线所需的边距。
- 若没有可靠闭合轮廓，不进行区域裁剪，避免误删非矩形或开放式草图。
- 区域筛选只减少远离主图的杂散线，不替代图元语义识别。

## 当前限制

- 这是自动几何转绘，不等于自动理解防雷工程语义；未分类几何统一进入简化图层。
- OCR 文字、手绘符号及尺寸线仍受照片质量影响。
- 若原图存在严重透视、遮挡、重叠或断笔，简化图本身可能漏检或误检。
- 当前自动输出目标是忠实复现简化图；后续再迭代结构线、接闪带、引下线等语义分类。
