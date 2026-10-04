from app.services.review_score import parcel_review_score


def test_review_score_is_deterministic_and_explainable():
    feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0,0],[10,0],[10,10],[0,10],[0,0]]]},
        "properties": {"parcel_id": "P-001", "confidence": 0.9, "review_required": False},
    }
    result = parcel_review_score(feature, [])
    assert result["review_score"] == 0.0
    assert result["review_priority"] == "LOW"
