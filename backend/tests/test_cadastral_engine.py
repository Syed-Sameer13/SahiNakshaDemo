from shapely.geometry import Polygon

from app.services.cadastral_engine import (
    compare_candidate_to_reference,
    enrich_cadastral_metrics,
    extract_raster_metadata,
    generate_candidate_parcels,
    map_to_pixel,
    pixel_to_map,
    clean_polygon_geometry,
)
from app.services.geojson_service import feature_collection


def test_valid_polygon_metrics_and_candidate_source():
    polygon = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0],[10,0],[10,10],[0,10],[0,0]]]}, "properties": {"parcel_id": "P-1"}}
    fc = feature_collection([polygon])
    out = enrich_cadastral_metrics(fc, "EPSG:3857")
    props = out["features"][0]["properties"]
    assert props["geometry_valid"] is True
    assert props["area_sq_m"] == 100.0
    assert props["parcel_perimeter"] == 40.0


def test_invalid_polygon_is_repaired():
    bowtie = Polygon([(0,0),(10,10),(0,10),(10,0),(0,0)])
    cleaned = clean_polygon_geometry(bowtie)
    assert cleaned is not None
    assert cleaned.is_valid


def test_overlapping_reference_comparison():
    a = {"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[10,0],[10,10],[0,10],[0,0]]]},"properties":{"parcel_id":"C-1"}}
    b = {"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[1,1],[9,1],[9,9],[1,9],[1,1]]]},"properties":{"parcel_id":"R-1"}}
    props = compare_candidate_to_reference(a, b, "EPSG:3857")
    assert props["reference_available"] is True
    assert props["intersection_over_union"] > 0
    assert props["discrepancy_status"] in {"MATCH","MINOR_DISCREPANCY","MAJOR_DISCREPANCY"}


def test_empty_geometry_is_removed():
    assert clean_polygon_geometry(Polygon()) is None


def test_missing_crs_does_not_fake_square_metres():
    fc = feature_collection([{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[10,0],[10,10],[0,10],[0,0]]]},"properties":{}}])
    out = enrich_cadastral_metrics(fc, None)
    props = out["features"][0]["properties"]
    assert props["area_sq_m"] is None
    assert props["area_status"] == "image_local_or_unknown"


def test_geographic_crs_does_not_report_source_degrees_as_square_metres():
    fc = feature_collection([{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[77,17],[77.001,17],[77.001,17.001],[77,17.001],[77,17]]]},"properties":{}}])
    out = enrich_cadastral_metrics(fc, "EPSG:4326")
    props = out["features"][0]["properties"]
    assert props["area_sq_m"] is None


def test_projected_crs_reports_metric_area():
    fc = feature_collection([{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[20,0],[20,10],[0,10],[0,0]]]},"properties":{}}])
    out = enrich_cadastral_metrics(fc, "EPSG:3857")
    assert out["features"][0]["properties"]["area_sq_m"] == 200.0


def test_pixel_map_round_trip():
    metadata = {"transform": [2,0,100,0,-2,200], "crs":"EPSG:3857"}
    mx, my = pixel_to_map(5, 10, metadata)
    px, py = map_to_pixel(mx, my, metadata)
    assert abs(px - 5) < 1e-9
    assert abs(py - 10) < 1e-9


def test_ai_candidate_blocks_are_explicitly_non_legal():
    ai = {"buildings": feature_collection([
        {"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[5,0],[5,5],[0,5],[0,0]]]},"properties":{"building_id":"B-1"}}
    ])}
    candidates = generate_candidate_parcels(ai)
    assert candidates["features"][0]["properties"]["legal_cadastral_boundary"] is False
