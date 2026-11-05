from lightningcad.ocr import parse_dimension_text


def test_parse_meters():
    result = parse_dimension_text("5.3m")
    assert result["value_mm"] == 5300
    assert result["unit"] == "m"


def test_parse_centimeters():
    result = parse_dimension_text("32cm")
    assert result["value_mm"] == 320


def test_unknown_unit_does_not_invent_scale():
    result = parse_dimension_text("42")
    assert result["value_mm"] is None
