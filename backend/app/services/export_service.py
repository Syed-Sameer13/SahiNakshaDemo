import json


def serialize_geojson(result):
    """Return a standards-shaped GeoJSON FeatureCollection for GIS consumers."""
    parcels = result.get("parcels") or {"type": "FeatureCollection", "features": []}
    if parcels.get("type") != "FeatureCollection":
        parcels = {"type": "FeatureCollection", "features": []}

    output = {
        "type": "FeatureCollection",
        "features": parcels.get("features", []),
        "analysis_id": result.get("analysis_id"),
        "analysis_mode": result.get("analysis_mode"),
        "cadastral_mode": result.get("cadastral_mode"),
        "validation": result.get("validation", {}),
        "topology_stats": result.get("topology_stats", {}),
        "review_summary": parcels.get("review_summary", {}),
        "area_summary": parcels.get("area_summary", {}),
        "legal_status": "prototype_output_requires_authoritative_cadastral_and_survey_validation",
    }
    return output


def to_json_bytes(result):
    return json.dumps(serialize_geojson(result), indent=2).encode("utf-8")
