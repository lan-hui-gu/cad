LINE_CATEGORIES = {
    "建筑结构": "building_structure",
    "明装接闪带": "exposed_air_termination",
    "暗装接闪带": "concealed_air_termination",
    "引下线": "down_conductor",
    "说明引线": "annotation_leader",
    "尺寸线/界线": "dimension_line",
    "不绘制": "ignore",
}

LINE_CATEGORY_LABELS = {value: label for label, value in LINE_CATEGORIES.items()}

CURVE_CATEGORIES = {
    "弧线": "arc",
    "不绘制": "ignore",
}

POINT_CATEGORIES = {
    "测点": "test_point",
    "接闪杆": "air_terminal_rod",
    "标高": "elevation",
    "引下线标记": "down_conductor_marker",
    "接地点": "grounding_point",
    "SPD": "spd",
    "金属构件": "metal_component",
    "金属管道": "metal_pipe",
    "不绘制": "ignore",
}

POINT_CATEGORY_LABELS = {value: label for label, value in POINT_CATEGORIES.items()}

LINE_LAYERS = {
    "building_structure": "建筑结构",
    "exposed_air_termination": "明装接闪带",
    "concealed_air_termination": "暗装接闪带",
    "down_conductor": "引下线",
    "annotation_leader": "说明引线",
    "dimension_line": "尺寸标注",
}

POINT_LAYERS = {
    "test_point": "测点",
    "air_terminal_rod": "接闪杆",
    "elevation": "标高",
    "down_conductor_marker": "引下线标记",
    "grounding_point": "接地点",
    "spd": "SPD",
    "metal_component": "金属构件",
    "metal_pipe": "金属管道",
}
