"""Select the best available SahiNaksha vision model at runtime."""
from .yolo_segmentation import run_yolo_segmentation
from .trained_segmentation import run_trained_segmentation
from .hotosm_building_segmentation import run_hotosm_building_segmentation
from .ai_segmentation import run_ai_segmentation as run_sam_segmentation


def run_ai_segmentation(image_path: str):
    """Prefer SahiNaksha-trained models, then the generic HOTOSM model, then SAM.

    The custom models must take priority so newly trained project-specific weights
    are actually used during the demo instead of being hidden behind a generic
    pretrained model.
    """
    yolo_result, yolo_info = run_yolo_segmentation(image_path)
    if yolo_result is not None:
        return yolo_result, yolo_info

    trained_result, trained_info = run_trained_segmentation(image_path)
    if trained_result is not None:
        trained_info = {
            **trained_info,
            "fallback_after_yolo": yolo_info["status"],
        }
        return trained_result, trained_info

    hotosm_result, hotosm_info = run_hotosm_building_segmentation(image_path)
    if hotosm_result is not None:
        hotosm_info = {
            **hotosm_info,
            "fallback_after_yolo": yolo_info["status"],
            "fallback_after_trained_model": trained_info["status"],
        }
        return hotosm_result, hotosm_info

    sam_result, sam_info = run_sam_segmentation(image_path)
    if sam_result is not None:
        sam_info = {
            **sam_info,
            "fallback_after_yolo": yolo_info["status"],
            "fallback_after_trained_model": trained_info["status"],
            "fallback_after_hotosm": hotosm_info["status"],
        }
        return sam_result, sam_info

    return None, {
        "provider": "none",
        "status": "Custom YOLO, trained pixel model, HOTOSM building model and SAM unavailable",
        "yolo": yolo_info["status"],
        "trained_model": trained_info["status"],
        "hotosm": hotosm_info["status"],
        "sam": sam_info["status"],
    }
