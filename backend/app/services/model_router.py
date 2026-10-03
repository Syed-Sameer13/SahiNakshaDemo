"""Reliable AI model orchestration for SahiNaksha."""
from __future__ import annotations

import logging
import os
from typing import Any

from .ai_pipeline import clean_ai_result, evidence_metadata, preprocess_image, utc_now
from .hotosm_building_segmentation import run_hotosm_building_segmentation
from .sam_refinement import refine_hotosm_result
from .ai_segmentation import run_ai_segmentation as run_sam_segmentation
from .yolo_segmentation import run_yolo_segmentation
from .trained_segmentation import run_trained_segmentation
from .opencv_analysis import extract_features

logger = logging.getLogger("sahinaksha.ai")


def _safe_call(name: str, fn, image_path: str):
    try:
        logger.info("AI stage=%s status=PROCESSING", name)
        result, info = fn(image_path)
        info = dict(info or {})
        if result is not None:
            info["status"] = "MODEL_AVAILABLE"
            logger.info("AI stage=%s status=%s", name, info.get("status"))
        else:
            info["status"] = "MODEL_UNAVAILABLE"
            logger.warning("AI stage=%s unavailable: %s", name, info.get("reason") or info.get("status"))
        return result, info
    except Exception as exc:
        logger.exception("AI stage=%s crashed", name)
        return None, {"provider": name, "status": "MODEL_UNAVAILABLE", "error": str(exc)}


def _version(env_name: str) -> str:
    return os.getenv(env_name, "unknown")


def run_ai_segmentation(image_path: str):
    """Run one primary learned pipeline, then learned alternatives, then OpenCV."""
    started = utc_now()
    if os.getenv("SAHINAKSHA_DISABLE_AI", "0") == "1":
        logger.info("AI disabled by configuration; activating deterministic fallback")
        fallback = extract_features(image_path)
        return fallback, {
            **evidence_metadata("opencv_deterministic", "OpenCV feature extractor", "FALLBACK_ACTIVE", "system"),
            "status": "FALLBACK_ACTIVE",
            "fallback_provider": "opencv_deterministic",
            "reason": "SAHINAKSHA_DISABLE_AI=1",
            "processing_started": started,
        }

    # Validate/read the raster before loading expensive models.
    _, preprocessing = preprocess_image(image_path)

    attempts: list[dict[str, Any]] = []
    primary_result = None

    hotosm_result, hotosm_info = _safe_call("hotosm_dinov3s_buildings", run_hotosm_building_segmentation, image_path)
    attempts.append({"provider": "hotosm_dinov3s_buildings", **hotosm_info})
    if hotosm_result is not None:
        primary_result, sam_info = refine_hotosm_result(image_path, hotosm_result)
        attempts.append({"provider": "sam_refinement", **sam_info})
        if sam_info.get("status") == "COMPLETED":
            primary_result, cleanup = clean_ai_result(primary_result)
            return primary_result, {
                **evidence_metadata(
                    "hotosm_dinov3s_buildings+segment_anything",
                    "HOTOSM DINOv3 building segmentation + SAM mask fusion",
                    "COMPLETED",
                    _version("SAHINAKSHA_HOTOSM_MODEL_VERSION"),
                ),
                "status": "COMPLETED",
                "processing_started": started,
                "preprocessing": preprocessing,
                "attempts": attempts,
                "cleanup": cleanup,
                "segmentation_masks_generated": True,
                "fallback_used": False,
                "parcel_note": "AI outputs are physical-feature evidence; parcel ownership boundaries remain human/GIS review tasks.",
            }
        logger.warning("HOTOSM succeeded but SAM refinement unavailable; retaining HOTOSM result")
        primary_result, cleanup = clean_ai_result(hotosm_result)
        return primary_result, {
            **evidence_metadata(
                "hotosm_dinov3s_buildings",
                "HOTOSM DINOv3 building segmentation",
                "COMPLETED",
                _version("SAHINAKSHA_HOTOSM_MODEL_VERSION"),
            ),
            "status": "COMPLETED",
            "processing_started": started,
            "preprocessing": preprocessing,
            "attempts": attempts,
            "cleanup": cleanup,
            "segmentation_masks_generated": True,
            "fallback_used": False,
            "sam_refinement": "MODEL_UNAVAILABLE",
            "parcel_note": "AI outputs are physical-feature evidence; parcel ownership boundaries remain human/GIS review tasks.",
        }

    # Independent SAM remains a learned alternative when HOTOSM is unavailable.
    sam_result, sam_info = _safe_call("segment_anything", run_sam_segmentation, image_path)
    attempts.append({"provider": "segment_anything", **sam_info})
    if sam_result is not None:
        sam_result, cleanup = clean_ai_result(sam_result)
        return sam_result, {
            **evidence_metadata("segment_anything", "Segment Anything Model", "COMPLETED", _version("SAHINAKSHA_SAM_MODEL_VERSION")),
            "status": "COMPLETED",
            "processing_started": started,
            "preprocessing": preprocessing,
            "attempts": attempts,
            "cleanup": cleanup,
            "segmentation_masks_generated": True,
            "fallback_used": False,
            "parcel_note": "SAM provides object/feature masks, not legal cadastral boundaries.",
        }

    # Preserve project-specific learned models as secondary optional providers.
    for name, fn, provider, version_env in (
        ("custom_yolo", run_yolo_segmentation, "sahinaksha_custom_yolo", "SAHINAKSHA_YOLO_MODEL_VERSION"),
        ("trained_pixel_model", run_trained_segmentation, "sahinaksha_trained_pixel_model", "SAHINAKSHA_PIXEL_MODEL_VERSION"),
    ):
        result, info = _safe_call(name, fn, image_path)
        attempts.append({"provider": provider, **info})
        if result is not None:
            result, cleanup = clean_ai_result(result)
            return result, {
                **evidence_metadata(provider, provider, "COMPLETED", _version(version_env)),
                "status": "COMPLETED",
                "processing_started": started,
                "preprocessing": preprocessing,
                "attempts": attempts,
                "cleanup": cleanup,
                "segmentation_masks_generated": True,
                "fallback_used": True,
                "fallback_type": "secondary_learned_model",
                "parcel_note": "AI outputs are preliminary feature evidence; final cadastral geometry requires human surveyor review.",
            }

    # Deterministic fallback must never prevent the application from returning a result.
    logger.warning("All learned AI providers unavailable; activating OpenCV fallback")
    fallback = extract_features(image_path)
    return fallback, {
        **evidence_metadata("opencv_deterministic", "OpenCV feature extractor", "FALLBACK_ACTIVE", "system"),
        "status": "FALLBACK_ACTIVE",
        "fallback_provider": "opencv_deterministic",
        "fallback_used": True,
        "processing_started": started,
        "preprocessing": preprocessing,
        "attempts": attempts,
        "segmentation_masks_generated": False,
        "parcel_note": "Deterministic image evidence only; final cadastral geometry requires human surveyor/GIS review.",
    }
