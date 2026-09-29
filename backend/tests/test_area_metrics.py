from app.services.area_metrics import feature_area_metrics


def test_local_area_is_not_labelled_square_metres():
    feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 5], [0, 5], [0, 0]]]},
        "properties": {},
    }
    result = feature_area_metrics(feature)
    assert result["area"] == 50.0
    assert result["area_sq_m"] is None
    assert result["area_status"] == "not_real_world"
