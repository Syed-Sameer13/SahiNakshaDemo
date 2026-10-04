from app.services.validation import validate_parcels


def parcel(parcel_id, coords, **props):
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]}, "properties": {"parcel_id": parcel_id, **props}}


def building(building_id, coords):
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]}, "properties": {"building_id": building_id}}


def test_validation_issue_schema_and_geometry_overlap():
    fc = {"type":"FeatureCollection","features":[
        parcel("P-1", [[0,0],[10,0],[10,10],[0,10],[0,0]], boundary_evidence=0.4),
        parcel("P-2", [[5,5],[15,5],[15,15],[5,15],[5,5]])]}
    result = validate_parcels(fc)
    assert result["issue_count"] > 0
    assert any(i["issue_type"] == "POLYGON_OVERLAP" for i in result["issues"])
    assert any(i["issue_type"] == "WEAK_BOUNDARY_EVIDENCE" for i in result["issues"])
    issue = result["issues"][0]
    assert set(("issue_id","parcel_id","issue_type","severity","description","evidence","status","created_timestamp")) <= issue.keys()


def test_validation_detects_duplicate_geometry():
    fc = {"type":"FeatureCollection","features":[
        parcel("P-1", [[0,0],[10,0],[10,10],[0,10],[0,0]]),
        parcel("P-2", [[0,0],[10,0],[10,10],[0,10],[0,0]])]}
    result = validate_parcels(fc)
    assert sum(i["issue_type"] == "DUPLICATE_GEOMETRY" for i in result["issues"]) == 2


def test_validation_detects_reference_mismatch_conditions():
    candidate = parcel("P-1", [[0,0],[12,0],[12,12],[0,12],[0,0]], percentage_area_difference=44.0, reference_parcel_id="R-1", discrepancy_status="MAJOR_DISCREPANCY")
    reference = parcel("R-1", [[0,0],[10,0],[10,10],[0,10],[0,0]])
    result = validate_parcels({"type":"FeatureCollection","features":[candidate]}, reference_parcels={"type":"FeatureCollection","features":[reference]})
    types = {i["issue_type"] for i in result["issues"]}
    assert "AREA_MISMATCH" in types
    assert "REFERENCE_MISMATCH" in types
    assert "CANDIDATE_OUTSIDE_REFERENCE" in types


def test_validation_detects_building_outside_candidate():
    fc = {"type":"FeatureCollection","features":[parcel("P-1", [[0,0],[10,0],[10,10],[0,10],[0,0]])]}
    buildings = {"type":"FeatureCollection","features":[building("B-1", [[20,20],[21,20],[21,21],[20,21],[20,20]])]}
    result = validate_parcels(fc, buildings=buildings)
    assert any(i["issue_type"] == "BUILDING_OUTSIDE_PARCEL" for i in result["issues"])


def test_review_priority_is_not_probability():
    from app.services.review_score import parcel_review_score
    result = parcel_review_score(
        parcel("P-1", [[0,0],[10,0],[10,10],[0,10],[0,0]], percentage_area_difference=14.2, discrepancy_status="MINOR_DISCREPANCY", boundary_evidence=0.3),
        [{"severity":"ERROR","issue_type":"POLYGON_OVERLAP"}])
    assert result["review_priority"] in {"LOW","MEDIUM","HIGH","CRITICAL"}
    assert "probability" in result["score_definition"]
    assert result["score_definition"].startswith("Deterministic")
