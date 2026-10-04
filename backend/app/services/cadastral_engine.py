"""CRS-aware cadastral candidate processing.

This module creates preliminary cadastral candidates for surveyor review. It never
interprets building footprints as legal parcel boundaries.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from shapely.geometry import box, mapping, shape, Polygon, MultiPoint
from shapely.ops import transform as shapely_transform, unary_union, voronoi_diagram
from pyproj import CRS, Transformer

from .geojson_service import feature_collection

logger = logging.getLogger("sahinaksha.gis")


def _image_size(image_path: str) -> tuple[int, int]:
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Unable to read raster image.")
    h, w = image.shape[:2]
    return w, h


def extract_raster_metadata(image_path: str) -> dict[str, Any]:
    """Extract raster metadata. Uses rasterio when available, image dimensions otherwise."""
    path = Path(image_path)
    try:
        import rasterio
        with rasterio.open(path) as src:
            return {
                "path": path.name,
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "dtype": str(src.dtypes[0]) if src.dtypes else None,
                "crs": src.crs.to_string() if src.crs else None,
                "transform": [float(v) for v in src.transform[:6]],
                "bounds": {
                    "left": float(src.bounds.left),
                    "bottom": float(src.bounds.bottom),
                    "right": float(src.bounds.right),
                    "top": float(src.bounds.top),
                },
                "resolution": [float(src.res[0]), float(src.res[1])],
                "georeferenced": bool(src.crs and src.transform),
                "area_units_available": bool(src.crs and not src.crs.is_geographic),
            }
    except ImportError:
        width, height = _image_size(image_path)
        return {
            "path": path.name,
            "width": width,
            "height": height,
            "count": 3,
            "dtype": None,
            "crs": None,
            "transform": None,
            "bounds": None,
            "resolution": None,
            "georeferenced": False,
            "area_units_available": False,
            "metadata_status": "rasterio_unavailable_for_georeferenced metadata",
        }
    except Exception as exc:
        logger.warning("Raster metadata extraction failed: %s", exc)
        width, height = _image_size(image_path)
        return {
            "path": path.name,
            "width": width,
            "height": height,
            "count": 3,
            "dtype": None,
            "crs": None,
            "transform": None,
            "bounds": None,
            "resolution": None,
            "georeferenced": False,
            "metadata_status": f"metadata_error: {exc}",
        }


def pixel_to_map(x: float, y: float, metadata: dict[str, Any]) -> tuple[float, float]:
    """Convert pixel coordinates to raster CRS coordinates when transform exists."""
    t = metadata.get("transform")
    if not t:
        raise ValueError("Raster transform is unavailable; pixel-to-map conversion is not possible.")
    a, b, cc, d, e, f = t
    return (a * x + b * y + cc, d * x + e * y + f)


def map_to_pixel(x: float, y: float, metadata: dict[str, Any]) -> tuple[float, float]:
    t = metadata.get("transform")
    if not t:
        raise ValueError("Raster transform is unavailable; map-to-pixel conversion is not possible.")
    a, b, cc, d, e, f = t
    matrix = np.array([[a, b], [d, e]], dtype=float)
    offset = np.array([cc, f], dtype=float)
    px, py = np.linalg.solve(matrix, np.array([x, y], dtype=float) - offset)
    return float(px), float(py)


def pixel_polygon_to_map(feature: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Vector feature coordinates are pixel x/y; transform every coordinate into map CRS."""
    if not metadata.get("transform") or not metadata.get("crs"):
        return feature

    def convert(x, y, z=None):
        mx, my = pixel_to_map(x, y, metadata)
        return (mx, my) if z is None else (mx, my, z)

    geom = shape(feature["geometry"])
    mapped = shapely_transform(convert, geom)
    result = dict(feature)
    result["geometry"] = mapping(mapped)
    result.setdefault("properties", {})["geometry_crs"] = metadata["crs"]
    return result


def _repair_geometry(geom, min_area: float = 0.000001):
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty:
        return None
    if geom.geom_type == "MultiPolygon":
        parts = [p for p in geom.geoms if p.is_valid and p.area >= min_area]
        if not parts:
            return None
        geom = max(parts, key=lambda p: p.area)
    if geom.geom_type != "Polygon" or geom.area < min_area:
        return None
    # buffer(0) also normalizes many duplicate/collinear vertex artifacts.
    return geom


def clean_polygon_geometry(geom, simplify_tolerance: float = 0.0, min_area: float = 0.000001):
    geom = _repair_geometry(geom, min_area)
    if geom is None:
        return None
    if simplify_tolerance > 0:
        geom = geom.simplify(simplify_tolerance, preserve_topology=True)
        geom = _repair_geometry(geom, min_area)
    return geom


def _load_geojson(path: str) -> tuple[list[dict[str, Any]], str | None]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
    source_crs = None
    crs_data = payload.get("crs")
    if isinstance(crs_data, dict):
        props = crs_data.get("properties") or {}
        source_crs = props.get("name") or props.get("href")
    return features, source_crs


def _reproject_geometry(geom, source_crs: str | None, target_crs: str | None):
    if not source_crs or not target_crs or source_crs == target_crs:
        return geom
    transformer = Transformer.from_crs(CRS.from_user_input(source_crs), CRS.from_user_input(target_crs), always_xy=True)
    return shapely_transform(transformer.transform, geom)


def _reference_crs(payload_crs: str | None) -> str | None:
    return payload_crs


def load_reference_parcels(reference_path: str, image_path: str):
    features, source_crs = _load_geojson(reference_path)
    metadata = extract_raster_metadata(image_path)
    raster_crs = metadata.get("crs")

    output = []
    for index, feature in enumerate(features, start=1):
        if not feature.get("geometry"):
            continue
        try:
            geom = shape(feature["geometry"])
            geom = _repair_geometry(geom)
            if geom is None:
                continue

            # Legacy image-local reference files remain supported.
            if source_crs is None and not raster_crs:
                minx, miny, maxx, maxy = geom.bounds
                if not (-0.5 <= minx <= 100.5 and -0.5 <= maxx <= 100.5 and -0.5 <= miny <= 100.5 and -0.5 <= maxy <= 100.5):
                    raise ValueError("Reference GeoJSON has no CRS and is not in supported 0..100 image-local coordinates.")
            elif source_crs and raster_crs:
                geom = _reproject_geometry(geom, source_crs, raster_crs)
            elif source_crs and not raster_crs:
                raise ValueError("Reference GeoJSON has a CRS but the raster has no CRS; spatial alignment is ambiguous.")
            else:
                raise ValueError("Raster has a CRS but reference GeoJSON has no CRS; refusing ambiguous spatial alignment.")

            props = dict(feature.get("properties") or {})
            parcel_id = str(props.get("parcel_id") or props.get("id") or f"P-{index:03d}")
            props.update({
                "parcel_id": parcel_id,
                "source": "existing_reference_gis",
                "reference_available": True,
                "review_required": True,
                "geometry_valid": bool(geom.is_valid),
            })
            output.append({"type": "Feature", "geometry": mapping(geom), "properties": props})
        except Exception as exc:
            logger.warning("Skipping reference parcel %s: %s", index, exc)

    result = feature_collection(output)
    if source_crs:
        result["source_crs"] = source_crs
    elif raster_crs:
        result["source_crs"] = raster_crs
    result["reference_metadata"] = {
        "available": bool(output),
        "source_crs": source_crs,
        "raster_crs": raster_crs,
        "count": len(output),
    }
    return result


def generate_candidate_parcels(ai_result: dict[str, Any], reference_parcels: dict[str, Any] | None = None):
    """Create non-legal candidate blocks from reference geometry or grouped AI evidence.

    Reference geometry is preferred. Without reference data, candidates are derived
    only as evidence blocks around spatially separated building footprints; they are
    explicitly marked as synthetic review candidates, never legal parcels.
    """
    if reference_parcels and reference_parcels.get("features"):
        candidates = []
        for f in reference_parcels["features"]:
            props = dict(f.get("properties") or {})
            geom = shape(f["geometry"])
            buildings = (ai_result.get("buildings") or {}).get("features", [])
            evidence_area = 0.0
            evidence_count = 0
            for building in buildings:
                try:
                    bg = shape(building["geometry"])
                    inter = geom.intersection(bg)
                    if not inter.is_empty and inter.area > 0:
                        evidence_area += inter.area
                        evidence_count += 1
                except Exception:
                    continue
            props.update({
                "source": "reference_gis_plus_ai_evidence",
                "reference_available": True,
                "candidate_type": "reference_based_candidate",
                "ai_evidence": "building_footprints",
                "ai_evidence_feature_count": evidence_count,
                "ai_evidence_overlap_area": evidence_area,
                "review_required": True,
                "legal_cadastral_boundary": False,
            })
            candidates.append({"type": "Feature", "geometry": f["geometry"], "properties": props})
        result = feature_collection(candidates)
        if reference_parcels.get("source_crs"):
            result["source_crs"] = reference_parcels["source_crs"]
        return result

    buildings = (ai_result.get("buildings") or {}).get("features", [])
    if not buildings:
        return feature_collection([])

    building_geoms = []
    building_props = []
    for f in buildings:
        g = _repair_geometry(shape(f["geometry"]))
        if g is not None and not g.is_empty:
            building_geoms.append(g)
            building_props.append(f.get("properties", {}))

    if not building_geoms:
        return feature_collection([])

    roads = (ai_result.get("roads") or {}).get("features", [])
    road_geoms = []
    for r in roads:
        try:
            rg = _repair_geometry(shape(r["geometry"]))
            if rg is not None and not rg.is_empty:
                road_geoms.append(rg.buffer(1.2))
        except Exception:
            pass

    road_union = unary_union(road_geoms) if road_geoms else Polygon()
    frame = box(0, 0, 100, 100)
    try:
        free_land = frame.difference(road_union)
    except Exception:
        free_land = frame

    candidates = []
    if len(building_geoms) > 1:
        try:
            centroids = [b.centroid for b in building_geoms]
            mp = MultiPoint(centroids)
            vor = voronoi_diagram(mp, envelope=frame)
            cells = list(vor.geoms) if hasattr(vor, "geoms") else [vor]
            
            for idx, (b_geom, b_prop) in enumerate(zip(building_geoms, building_props), start=1):
                c = b_geom.centroid
                matched_cell = None
                for cell in cells:
                    if cell.contains(c) or cell.intersects(c):
                        matched_cell = cell
                        break
                
                compound = b_geom.buffer(6.0)
                if matched_cell is not None:
                    plot = compound.union(b_geom.buffer(2.0)).intersection(matched_cell)
                else:
                    plot = compound
                
                plot = plot.intersection(free_land)
                plot = _repair_geometry(plot)
                if plot is not None and not plot.is_empty and plot.area >= 0.5:
                    simplified = plot.simplify(0.18, preserve_topology=True)
                    candidates.append({
                        "type": "Feature",
                        "geometry": mapping(simplified),
                        "properties": {
                            "parcel_id": f"P-{idx:03d}",
                            "source": "ai_compound_boundary_synthesis",
                            "reference_available": False,
                            "candidate_type": "compound_property_plot",
                            "assigned_building": b_prop.get("building_id", f"B-{idx:03d}"),
                            "review_required": True,
                            "legal_cadastral_boundary": False,
                        }
                    })
        except Exception as exc:
            logger.warning("Voronoi compound synthesis fallback: %s", exc)

    if not candidates:
        for idx, (b_geom, b_prop) in enumerate(zip(building_geoms, building_props), start=1):
            plot = _repair_geometry(b_geom.buffer(5.0).intersection(free_land))
            if plot is not None and not plot.is_empty:
                candidates.append({
                    "type": "Feature",
                    "geometry": mapping(plot.simplify(0.18, preserve_topology=True)),
                    "properties": {
                        "parcel_id": f"P-{idx:03d}",
                        "source": "ai_compound_boundary_synthesis",
                        "reference_available": False,
                        "candidate_type": "compound_property_plot",
                        "assigned_building": b_prop.get("building_id", f"B-{idx:03d}"),
                        "review_required": True,
                        "legal_cadastral_boundary": False,
                    }
                })

    return feature_collection(candidates)


def compare_candidate_to_reference(candidate: dict[str, Any], reference: dict[str, Any] | None, source_crs: str | None = None):
    props = candidate.setdefault("properties", {})
    if reference is None:
        props.update({"reference_available": False, "discrepancy_status": "NO_REFERENCE"})
        return props

    cgeom = _repair_geometry(shape(candidate["geometry"]))
    rgeom = _repair_geometry(shape(reference["geometry"]))
    if cgeom is None or rgeom is None:
        props.update({"reference_available": True, "discrepancy_status": "MAJOR_DISCREPANCY"})
        return props

    inter = cgeom.intersection(rgeom).area
    union = cgeom.union(rgeom).area
    candidate_area = cgeom.area
    reference_area = rgeom.area
    abs_diff = abs(candidate_area - reference_area)
    pct_diff = abs_diff / reference_area * 100 if reference_area else None

    # Boundary displacement proxy: symmetric average Hausdorff distance.
    displacement = (cgeom.boundary.hausdorff_distance(rgeom.boundary) + rgeom.boundary.hausdorff_distance(cgeom.boundary)) / 2

    if pct_diff is None or pct_diff > 30 or (inter / union if union else 0) < 0.50:
        status = "MAJOR_DISCREPANCY"
    elif pct_diff > 10 or (inter / union if union else 0) < 0.80:
        status = "MINOR_DISCREPANCY"
    else:
        status = "MATCH"

    props.update({
        "reference_available": True,
        "reference_parcel_id": reference.get("properties", {}).get("parcel_id"),
        "reference_area": reference_area,
        "candidate_area": candidate_area,
        "absolute_area_difference": abs_diff,
        "percentage_area_difference": pct_diff,
        "intersection_area": inter,
        "intersection_over_union": inter / union if union else None,
        "boundary_displacement": displacement,
        "discrepancy_status": status,
        "discrepancy_crs": source_crs,
    })
    return props


def compare_to_references(candidates: dict[str, Any], references: dict[str, Any]):
    refs = references.get("features", [])
    for candidate in candidates.get("features", []):
        cgeom = shape(candidate["geometry"])
        best = None
        best_iou = 0.0
        for ref in refs:
            try:
                rgeom = shape(ref["geometry"])
                inter = cgeom.intersection(rgeom).area
                union = cgeom.union(rgeom).area
                iou = inter / union if union else 0.0
                if iou > best_iou:
                    best_iou, best = iou, ref
            except Exception:
                continue
        compare_candidate_to_reference(candidate, best, candidates.get("source_crs"))
    return candidates


def enrich_cadastral_metrics(parcels: dict[str, Any], source_crs: str | None = None):
    """Attach safe parcel metrics; square metres only when CRS is metric/projectable."""
    for feature in parcels.get("features", []):
        geom = shape(feature["geometry"])
        props = feature.setdefault("properties", {})
        props["parcel_area"] = float(geom.area)
        props["parcel_perimeter"] = float(geom.length)
        props["geometry_valid"] = bool(geom.is_valid)
        if source_crs:
            try:
                crs = CRS.from_user_input(source_crs)
                if crs.is_projected and crs.axis_info and "metre" in (crs.axis_info[0].unit_name or "").lower():
                    props["area_sq_m"] = float(geom.area)
                    props["perimeter_m"] = float(geom.length)
                    props["area_status"] = "available"
                else:
                    props["area_sq_m"] = None
                    props["perimeter_m"] = None
                    props["area_status"] = "not_metric"
            except Exception:
                props["area_sq_m"] = None
                props["perimeter_m"] = None
                props["area_status"] = "crs_error"
        else:
            props["area_sq_m"] = None
            props["perimeter_m"] = None
            props["area_status"] = "image_local_or_unknown"
    return parcels


def enrich_review_priority(parcels: dict[str, Any]):
    for feature in parcels.get("features", []):
        props = feature.setdefault("properties", {})
        score = 0
        if not props.get("geometry_valid", False): score += 40
        if props.get("discrepancy_status") == "MAJOR_DISCREPANCY": score += 35
        elif props.get("discrepancy_status") == "MINOR_DISCREPANCY": score += 15
        if props.get("intersection_over_union") is not None and props["intersection_over_union"] < 0.8: score += 15
        if not props.get("reference_available", False): score += 10
        if props.get("ai_evidence"): score += 5
        props["review_priority"] = min(100, score)
        props["review_required"] = True
    return parcels


def _scale_to_image(point: tuple[float, ...], width: int, height: int) -> tuple[int, int]:
    x, y = point[:2]
    if 0 <= x <= 100 and 0 <= y <= 100 and (width > 100 or height > 100):
        px = int(round(x * width / 100.0))
        py = int(round((100.0 - y) * height / 100.0))
    else:
        px = int(round(x))
        py = int(round(y))
    px = max(0, min(width - 1, px))
    py = max(0, min(height - 1, py))
    return px, py


def classify_parcel_landuse(parcels: dict[str, Any], image_path: str) -> dict[str, Any]:
    image = cv2.imread(image_path)
    if image is None:
        return parcels
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([30, 35, 20]), np.array([95, 255, 255]))

    for feature in parcels.get("features", []):
        try:
            geometry = shape(feature["geometry"])
            mask = np.zeros((height, width), dtype=np.uint8)
            if geometry.geom_type == "Polygon":
                pts = [_scale_to_image((x, y), width, height) for x, y in geometry.exterior.coords]
            elif geometry.geom_type == "MultiPolygon":
                pts = []
                for p in geometry.geoms:
                    pts.extend([_scale_to_image((x, y), width, height) for x, y in p.exterior.coords])
            else:
                continue
            if len(pts) < 3:
                continue
            cv2.fillPoly(mask, [np.array(pts, dtype=np.int32)], 255)
            area = max(1, cv2.countNonZero(mask))
            green_ratio = cv2.countNonZero(cv2.bitwise_and(mask, green)) / area
            if green_ratio > 0.60:
                land_use = "Vegetated/Open"
            elif green_ratio < 0.18:
                land_use = "Built-up"
            else:
                land_use = "Mixed Urban"
            feature.setdefault("properties", {})["land_use"] = land_use
            feature["properties"]["vegetation_ratio"] = round(float(green_ratio), 2)
        except Exception as exc:
            logger.debug("Landuse classification skipped for parcel: %s", exc)

    return parcels


def classify_parcel_height(parcels: dict[str, Any], dsm_path: str) -> dict[str, Any]:
    """Attach relative height evidence from an aligned DSM/height raster."""
    dsm = cv2.imread(dsm_path, cv2.IMREAD_GRAYSCALE)
    if dsm is None:
        return parcels
    height, width = dsm.shape[:2]

    for feature in parcels.get("features", []):
        try:
            geometry = shape(feature["geometry"])
            mask = np.zeros((height, width), dtype=np.uint8)
            if geometry.geom_type == "Polygon":
                pts = [_scale_to_image((x, y), width, height) for x, y in geometry.exterior.coords]
            elif geometry.geom_type == "MultiPolygon":
                pts = []
                for p in geometry.geoms:
                    pts.extend([_scale_to_image((x, y), width, height) for x, y in p.exterior.coords])
            else:
                continue
            if len(pts) < 3:
                continue
            cv2.fillPoly(mask, [np.array(pts, dtype=np.int32)], 255)
            values = dsm[mask > 0]
            if len(values):
                feature.setdefault("properties", {})["relative_height_mean"] = round(float(np.mean(values)), 2)
                feature["properties"]["height_source"] = "aligned_dsm"
        except Exception as exc:
            logger.debug("Height classification skipped for parcel: %s", exc)
    return parcels
