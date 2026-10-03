"""SAM refinement/fusion stage for HOTOSM building evidence.

The repository's existing SAM implementation uses automatic masks. This stage
does not claim SAM can infer ownership boundaries. It refines physical building
footprint evidence produced by HOTOSM by retaining overlapping SAM candidates.
"""
from __future__ import annotations

import logging
from typing import Any

import cv2
from shapely.geometry import shape

from .ai_segmentation import run_ai_segmentation

logger = logging.getLogger("sahinaksha.ai.sam")


def refine_hotosm_result(image_path: str, base_result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        sam_result, sam_info = run_ai_segmentation(image_path)
    except Exception as exc:
        logger.exception("SAM refinement failed")
        return base_result, {"status": "MODEL_UNAVAILABLE", "reason": str(exc)}

    if sam_result is None:
        return base_result, {"status": "MODEL_UNAVAILABLE", "reason": sam_info.get("status", "SAM unavailable")}

    base_features = (base_result.get("buildings") or {}).get("features", [])
    sam_features = (sam_result.get("buildings") or {}).get("features", [])
    if not base_features or not sam_features:
        return base_result, {
            "status": "COMPLETED",
            "method": "sam_automatic_mask_fusion",
            "base_buildings": len(base_features),
            "sam_buildings": len(sam_features),
            "accepted_refinements": 0,
        }

    refined = []
    accepted = 0
    for base in base_features:
        base_geom = shape(base["geometry"])
        best = None
        best_iou = 0.0
        for candidate in sam_features:
            candidate_geom = shape(candidate["geometry"])
            inter = base_geom.intersection(candidate_geom).area
            union = base_geom.union(candidate_geom).area
            iou = inter / max(union, 1e-9)
            if iou > best_iou:
                best_iou = iou
                best = candidate
        if best is not None and best_iou >= 0.25:
            merged = dict(best)
            props = dict(merged.get("properties") or {})
            props.update({
                "feature_type": "building_footprint",
                "model_source": "hotosm_dinov3s_buildings+segment_anything",
                "refinement_iou": round(best_iou, 4),
                "confidence": props.get("confidence") if isinstance(props.get("confidence"), (int, float)) else None,
                "confidence_available": isinstance(props.get("confidence"), (int, float)),
                "review_required": True,
            })
            merged["properties"] = props
            refined.append(merged)
            accepted += 1
        else:
            refined.append(base)

    result = dict(base_result)
    result["buildings"] = {"type": "FeatureCollection", "features": refined}
    return result, {
        "status": "COMPLETED",
        "method": "hotosm_anchors_with_sam_mask_fusion",
        "base_buildings": len(base_features),
        "sam_buildings": len(sam_features),
        "accepted_refinements": accepted,
        "sam_source_status": sam_info.get("status"),
    }
