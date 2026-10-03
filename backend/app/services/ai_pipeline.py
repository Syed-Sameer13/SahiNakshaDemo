"""Shared preprocessing, polygon cleanup and AI evidence metadata.

The AI pipeline produces preliminary physical-feature evidence. It does not create
legal cadastral/ownership boundaries.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from shapely.geometry import shape, mapping
from shapely.validation import explain_validity

logger = logging.getLogger("sahinaksha.ai")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def preprocess_image(image_path: str) -> tuple[np.ndarray, dict[str, Any]]:
    """Read an RGB raster and apply conservative, model-neutral preprocessing."""
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unable to read supported raster image: {image_path}")

    # Keep original dimensions; normalize only contrast for model inputs that need it.
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    prepared = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    return prepared, {
        "input_format": Path(image_path).suffix.lower().lstrip("."),
        "input_size": [int(image.shape[1]), int(image.shape[0])],
        "preprocessing": "BGR read + conservative CLAHE luminance normalization",
    }


def _feature_key(feature: dict[str, Any]) -> str:
    props = feature.get("properties") or {}
    return str(
        props.get("building_id")
        or props.get("road_id")
        or props.get("parcel_id")
        or feature.get("id")
        or ""
    )


def _clean_feature(feature: dict[str, Any], simplify_tolerance: float, min_area: float) -> dict[str, Any] | None:
    geometry = feature.get("geometry")
    if not geometry:
        return None
    try:
        geom = shape(geometry)
    except Exception:
        return None
    if geom.is_empty:
        return None
    if not geom.is_valid:
        logger.info("Repairing invalid AI geometry: %s", explain_validity(geom))
        geom = geom.buffer(0)
    if geom.is_empty:
        return None
    if simplify_tolerance > 0:
        geom = geom.simplify(simplify_tolerance, preserve_topology=True)
    if geom.is_empty:
        return None

    if geom.geom_type == "MultiPolygon":
        parts = [p for p in geom.geoms if not p.is_empty and p.area >= min_area]
        if not parts:
            return None
        geom = max(parts, key=lambda p: p.area)

    if geom.geom_type != "Polygon":
        return None
    if geom.area < min_area:
        return None

    cleaned = dict(feature)
    cleaned["geometry"] = mapping(geom)
    props = dict(cleaned.get("properties") or {})
    props["geometry_valid"] = bool(geom.is_valid)
    props["boundary_evidence"] = props.get("boundary_evidence", props.get("edge_support"))
    cleaned["properties"] = props
    return cleaned


def clean_feature_collection(collection: dict[str, Any], feature_kind: str) -> tuple[dict[str, Any], dict[str, int]]:
    """Remove noise, repair geometry, simplify and deduplicate polygons."""
    features = collection.get("features", []) if isinstance(collection, dict) else []
    image_area = float(os.getenv("SAHINAKSHA_MIN_FEATURE_AREA", "0.0005"))
    simplify = float(os.getenv("SAHINAKSHA_SIMPLIFY_TOLERANCE", "0.03"))

    cleaned: list[dict[str, Any]] = []
    seen: list[Any] = []
    removed_noise = 0
    removed_duplicates = 0
    repaired = 0

    for feature in features:
        original_geom = feature.get("geometry")
        item = _clean_feature(feature, simplify, image_area)
        if item is None:
            removed_noise += 1
            continue
        if original_geom != item.get("geometry"):
            repaired += 1
        geom = shape(item["geometry"])

        duplicate = False
        for prior in seen:
            if geom.equals(prior) or geom.intersection(prior).area / max(min(geom.area, prior.area), 1e-9) >= 0.92:
                duplicate = True
                break
        if duplicate:
            removed_duplicates += 1
            continue

        seen.append(geom)
        props = item.setdefault("properties", {})
        props["geometry_cleanup"] = {
            "noise_removed": True,
            "simplified": simplify > 0,
            "deduplicated": True,
        }
        cleaned.append(item)

    logger.info(
        "AI geometry cleanup kind=%s input=%d output=%d noise=%d duplicates=%d repaired=%d",
        feature_kind, len(features), len(cleaned), removed_noise, removed_duplicates, repaired,
    )
    return {"type": "FeatureCollection", "features": cleaned}, {
        "input": len(features),
        "output": len(cleaned),
        "removed_noise": removed_noise,
        "removed_duplicates": removed_duplicates,
        "repaired_or_simplified": repaired,
    }


def clean_ai_result(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize learned-model output before it reaches GIS validation."""
    cleanup = {}
    for key, kind in (("buildings", "building"), ("parcels", "parcel")):
        result[key], cleanup[key] = clean_feature_collection(result.get(key) or {"type": "FeatureCollection", "features": []}, kind)
    # Roads may be LineStrings and therefore are intentionally not passed through polygon cleanup.
    result.setdefault("roads", {"type": "FeatureCollection", "features": []})
    return result, cleanup


def evidence_metadata(provider: str, model_name: str, status: str, version: str | None = None) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "model_version": version or "unknown",
        "model_provider": provider,
        "processing_timestamp": utc_now(),
        "processing_status": status,
        "legal_cadastral_boundary": False,
        "evidence_type": "preliminary physical-feature/boundary evidence",
    }
