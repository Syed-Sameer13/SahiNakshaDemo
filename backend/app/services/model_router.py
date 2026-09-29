"""Select the advanced pretrained vision pipeline at runtime."""
from .hotosm_building_segmentation import run_hotosm_building_segmentation
from .ai_segmentation import run_ai_segmentation as run_sam_segmentation
from .sam_refinement import refine_hotosm_buildings


def run_ai_segmentation(image_path: str):
    """HOTOSM/DINOv3 proposes buildings; SAM refines their boundaries.

    Project-specific YOLO/pixel models are compatibility fallbacks only.
    """
    hotosm_result, hotosm_info = run_hotosm_building_segmentation(image_path)

    if hotosm_result is not None:
        buildings = hotosm_result.get(
            "buildings",
            {"type": "FeatureCollection", "features": []},
        )
        refined, refinement_info = refine_hotosm_buildings(image_path, buildings)
        hotosm_result["buildings"] = refined
        hotosm_info = {
            **hotosm_info,
            "provider": "hotosm_dinov3s_buildings",
            "boundary_refinement": refinement_info,
            "strategy": refinement_info.get(
                "strategy",
                "hotosm_candidate_plus_sam_boundary_refinement",
            ),
        }
        return hotosm_result, hotosm_info

    # If HOTOSM is unavailable, use the existing standalone SAM pipeline.
    sam_result, sam_info = run_sam_segmentation(image_path)
    if sam_result is not None:
        return sam_result, {
            **sam_info,
            "fallback_after_hotosm": hotosm_info.get("status"),
            "strategy": "standalone_sam_fallback",
        }

    # Compatibility fallbacks: these are deliberately not the preferred path.
    try:
        from .yolo_segmentation import run_yolo_segmentation
        yolo_result, yolo_info = run_yolo_segmentation(image_path)
    except Exception as exc:
        yolo_result, yolo_info = None, {"status": f"YOLO fallback unavailable: {exc}"}
    if yolo_result is not None:
        return yolo_result, {
            **yolo_info,
            "fallback_after_hotosm": hotosm_info.get("status"),
            "fallback_after_sam": sam_info.get("status"),
            "strategy": "custom_yolo_compatibility_fallback",
        }

    try:
        from .trained_segmentation import run_trained_segmentation
        trained_result, trained_info = run_trained_segmentation(image_path)
    except Exception as exc:
        trained_result, trained_info = None, {"status": f"trained fallback unavailable: {exc}"}
    if trained_result is not None:
        return trained_result, {
            **trained_info,
            "fallback_after_hotosm": hotosm_info.get("status"),
            "fallback_after_sam": sam_info.get("status"),
            "fallback_after_yolo": yolo_info.get("status"),
            "strategy": "trained_pixel_compatibility_fallback",
        }

    return None, {
        "provider": "none",
        "status": "Advanced HOTOSM/SAM pipeline unavailable",
        "hotosm": hotosm_info.get("status"),
        "sam": sam_info.get("status"),
        "yolo": yolo_info.get("status"),
        "trained_model": trained_info.get("status"),
    }
