from __future__ import annotations

from typing import Any
from shapely.geometry import shape


def _numeric_area(feature: dict[str, Any]) -> float:
    geometry = feature.get("geometry")
    if not geometry:
        return 0.0
    try:
        return float(shape(geometry).area)
    except Exception:
        return 0.0


def feature_area_metrics(feature: dict[str, Any], source_crs: str | None = None) -> dict[str, Any]:
    """Return safe area metadata without pretending image-local units are square metres."""
    area = _numeric_area(feature)
    props = feature.setdefault("properties", {})

    if source_crs:
        try:
            from pyproj import CRS, Transformer
            from shapely.ops import transform

            crs = CRS.from_user_input(source_crs)
            if crs.is_geographic:
                # Pick a local UTM zone from the feature centroid.
                geom = shape(feature["geometry"])
                lon = float(geom.centroid.x)
                lat = float(geom.centroid.y)
                zone = int((lon + 180) // 6) + 1
                epsg = 32600 + zone if lat >= 0 else 32700 + zone
                transformer = Transformer.from_crs(crs, CRS.from_epsg(epsg), always_xy=True)
                projected = transform(transformer.transform, geom)
                return {
                    "area": round(area, 4),
                    "area_unit": "source_crs_units",
                    "area_sq_m": round(float(projected.area), 3),
                    "area_status": "computed_projected",
                    "area_crs": f"EPSG:{epsg}",
                }
            if crs.is_projected:
                # A projected CRS is assumed to use metres only when its linear
                # unit is metre; otherwise we refuse to label it m².
                unit = crs.axis_info[0].unit_name if crs.axis_info else ""
                if "metre" in (unit or "").lower() or "meter" in (unit or "").lower():
                    return {
                        "area": round(area, 4),
                        "area_unit": "projected",
                        "area_sq_m": round(area, 3),
                        "area_status": "computed_projected",
                        "area_crs": crs.to_string(),
                    }
                return {
                    "area": round(area, 4),
                    "area_unit": unit or "projected_units",
                    "area_status": "projected_non_metric",
                    "area_crs": crs.to_string(),
                }
        except Exception as exc:
            return {
                "area": round(area, 4),
                "area_unit": "unknown",
                "area_status": "crs_error",
                "area_crs": source_crs,
                "area_error": str(exc),
            }

    return {
        "area": round(area, 4),
        "area_unit": "image_local_units_squared",
        "area_status": "not_real_world",
        "area_sq_m": None,
        "area_note": "Real-world square metres require a valid source CRS/georeferencing.",
    }


def enrich_feature_areas(feature_collection: dict[str, Any], source_crs: str | None = None) -> dict[str, Any]:
    features = feature_collection.get("features", [])
    statuses: dict[str, int] = {}
    for feature in features:
        metrics = feature_area_metrics(feature, source_crs)
        feature.setdefault("properties", {}).update(metrics)
        statuses[metrics["area_status"]] = statuses.get(metrics["area_status"], 0) + 1

    feature_collection["area_summary"] = {
        "feature_count": len(features),
        "statuses": statuses,
        "source_crs": source_crs,
    }
    return feature_collection
