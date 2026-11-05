from lightningcad.simplify import simplify_segments


def test_reference_plan_preserves_upper_x_and_multiple_rectangular_frames():
    raw = [
        {"id":"u1","start":[82,15],"end":[82,105]},
        {"id":"u2","start":[83,15],"end":[83,105]},
        {"id":"v1","start":[135,15],"end":[135,105]},
        {"id":"v2","start":[136,15],"end":[136,105]},
        {"id":"t1","start":[82,15],"end":[135,15]},
        {"id":"t2","start":[82,16],"end":[135,16]},
        {"id":"b1","start":[82,105],"end":[135,105]},
        {"id":"b2","start":[82,106],"end":[135,106]},
        {"id":"x1","start":[82,15],"end":[135,105]},
        {"id":"x2","start":[135,15],"end":[82,105]},
        {"id":"long1","start":[82,105],"end":[82,312]},
        {"id":"long2","start":[135,105],"end":[135,312]},
        {"id":"midtop","start":[42,312],"end":[159,312]},
        {"id":"midbottom","start":[42,413],"end":[159,413]},
        {"id":"midleft","start":[42,312],"end":[42,413]},
        {"id":"midcentre","start":[101,312],"end":[101,413]},
        {"id":"midright","start":[159,312],"end":[159,413]},
        {"id":"lowerleft","start":[74,413],"end":[74,483]},
        {"id":"lowerright","start":[129,413],"end":[129,483]},
        {"id":"lowerbottom","start":[74,483],"end":[129,483]},
        {"id":"dimv","start":[19,15],"end":[19,413]},
        {"id":"dimh","start":[42,295],"end":[159,295]},
    ]
    simplified = simplify_segments(raw)
    assert len(simplified) > 20
    assert any(item["orientation"] == "oblique" for item in simplified)
    assert any(item.get("intersection_count", 0) for item in simplified)
    assert any(abs(item["start"][0]-82)<1 and abs(item["end"][0]-82)<1 for item in simplified)
    assert any(abs(item["start"][0]-135)<1 and abs(item["end"][0]-135)<1 for item in simplified)


def test_close_parallel_paths_are_not_merged_by_transitive_chaining():
    raw = [
        {"id":"a","start":[10,0],"end":[10,100]},
        {"id":"b","start":[13,0],"end":[13,100]},
        {"id":"c","start":[16,0],"end":[16,100]},
    ]
    simplified = simplify_segments(raw, offset_tolerance_px=2.0, split_intersections=False)
    assert len(simplified) == 3
