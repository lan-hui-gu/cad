import math

import pytest

from lightningcad.geometry import calibrate_mm_per_px, fit_circle, snap_near_orthogonal


def test_snap_near_horizontal():
    a, b, label = snap_near_orthogonal((0, 1), (100, 4))
    assert label == "snapped_horizontal"
    assert a[1] == pytest.approx(b[1])


def test_snap_near_vertical():
    a, b, label = snap_near_orthogonal((2, 0), (4, 100))
    assert label == "snapped_vertical"
    assert a[0] == pytest.approx(b[0])


def test_oblique_is_preserved():
    a, b, label = snap_near_orthogonal((0, 0), (100, 40))
    assert label == "preserved_oblique"
    assert a == [0.0, 0.0]
    assert b == [100.0, 40.0]


def test_circle_fit():
    points = [
        [100 + 50 * math.cos(i * math.pi / 20), 100 + 50 * math.sin(i * math.pi / 20)]
        for i in range(21)
    ]
    result = fit_circle(points)
    assert result["geometry"] == "arc_candidate"
    assert result["fit"]["radius"] == pytest.approx(50, rel=0.02)


def test_scale():
    assert calibrate_mm_per_px(100, 5300) == pytest.approx(53)
    with pytest.raises(ValueError):
        calibrate_mm_per_px(0, 5300)
