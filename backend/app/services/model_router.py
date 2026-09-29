"""Select the strongest available advanced vision pipeline at runtime."""
from .yolo_segmentation import run_yolo_segmentation
from .trained_segmentation import run_trained_segmentation
from .hotosm_building_segmentation import run_hotosm_building_segmentation
from .ai_segmentation import run_ai_segmentation as run_sam_segmentation
from .sam_refinement import refine_hotosm_buildings


def run_ai_segmentation(image_path: str):
    """Prefer HOTOSM semantic detection + SAM boundary refinement.

    Custom project-specific models remain a last-resort fallback. This keeps the
    prototype aligned with the documented advanced pretrained-model strategy.
    """
    hotosm_result, hotosm_info = run_hotosm_building_segmentation(image_path)
    if hotosm_result is not None:
        buildings = hotosm_result.get("buildings", {"type": "FeatureCollection", "features": []})
        refined_buildings, refinement_info = refine_hotosm_buildings(image_path, buildings)
        hotosm_result["buildings"] = refined_buildings
        return hotosm_result, {
            **hotosm_info,
            "provider": "hotosm_dinov3s_buildings",
            "boundary_refinement": refinement_info,
            "strategy": refinement_info.get(
                "strategy",
                "hotosm_candidate_plus_sam_boundary_refinement",
            ),
        }

    sam_result, sam_info = run_sam_segmentation(image_path)
    if sam_result is not None:
        return sam_result, {
            **sam_info,
            "fallback_after_hotosm": hotosm_info.get("status"),
            "strategy": "standalone_sam_fallback",
        }

    yolo_result, yolo_info = run_yolo_segmentation(image_path)
    if yolo_result is not None:
        return yolo_result, {
            **yolo_info,
            "fallback_after_hotosm": hotosm_info.get("status"),
            "fallback_after_sam": sam_info.get("status"),
            "strategy": "custom_yolo_fallback",
        }

    trained_result, trained_info = run_trained_segmentation(image_path)
    if trained_result is not None:
        return trained_result, {
            **trained_info,
            "fallback_after_hotosm": hotosm_info.get("status"),
            "fallback_after_sam": sam_info.get("status"),
            "fallback_after_yolo": yolo_info.get("status"),
            "strategy": "trained_pixel_model_fallback",
        }

    return None, {
        "provider": "none",
        "status": "HOTOSM, SAM, custom YOLO and trained pixel model unavailable",
        "hotosm": hotosm_info.get("status"),
        "sam": sam_info.get("status"),
        "yolo": yolo_info.get("status"),
        "trained_model": trained_info.get("status"),
    }
