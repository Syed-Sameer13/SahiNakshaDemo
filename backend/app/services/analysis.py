from pathlib import Path
from .opencv_analysis import extract_features
from .model_router import run_ai_segmentation
from .validation import validate_parcels
from .topology_engine import repair_and_validate_parcels
from .metrics import evaluate_against_ground_truth
from .area_metrics import enrich_feature_areas
from .review_score import enrich_review_scores
from .cadastral_engine import (
    load_reference_parcels,
    generate_candidate_parcels,
    compare_to_references,
    enrich_cadastral_metrics,
    enrich_review_priority,
    extract_raster_metadata,
    classify_parcel_landuse,
    classify_parcel_height,
)


def analyze_image(
    image_path: str,
    reference_parcels_path: str | None = None,
    ground_truth_path: str | None = None,
    dsm_path: str | None = None,
):
    raster_metadata = extract_raster_metadata(image_path)
    ai_result, ai_info = run_ai_segmentation(image_path)

    if ai_result is not None:
        result = ai_result
        provider = ai_info.get("provider", "ai")
        extraction_mode = "trained_segmentation" if provider == "sahinaksha_trained_pixel_model" else "ai_segmentation"
    else:
        result = extract_features(image_path)
        extraction_mode = "opencv_fallback"

    reference_result = None
    if reference_parcels_path:
        reference_result = load_reference_parcels(reference_parcels_path, image_path)
        result["reference_parcels"] = reference_result

    result["parcels"] = generate_candidate_parcels(result, reference_result)
    if reference_result and reference_result.get("features"):
        result["parcels"] = compare_to_references(result["parcels"], reference_result)
        result["cadastral_mode"] = "reference_gis_plus_ai_evidence"
    else:
        result["cadastral_mode"] = "preliminary_ai_evidence_candidates"

    result.setdefault("parcels", {"type": "FeatureCollection", "features": []})
    result["parcels"], topology_stats = repair_and_validate_parcels(result["parcels"])
    result["parcels"] = classify_parcel_landuse(result["parcels"], image_path)

    if dsm_path:
        result["parcels"] = classify_parcel_height(result["parcels"], dsm_path)

    result["validation"] = validate_parcels(result["parcels"])
    source_crs = result["parcels"].get("source_crs") if isinstance(result.get("parcels"), dict) else None
    result["parcels"] = enrich_feature_areas(result["parcels"], source_crs)
    result["parcels"] = enrich_cadastral_metrics(result["parcels"], result["parcels"].get("source_crs") or raster_metadata.get("crs"))
    result["parcels"] = enrich_review_priority(result["parcels"])
    result["parcels"] = enrich_review_scores(result["parcels"], result["validation"])
    result["raster_metadata"] = raster_metadata
    result["analysis_mode"] = extraction_mode
    result["ai_engine"] = ai_info
    result["ai_status"] = ai_info.get("status", "FAILED")
    result["model_metadata"] = {
        "model_name": ai_info.get("model_name", ai_info.get("provider", "unknown")),
        "model_version": ai_info.get("model_version", "unknown"),
        "processing_timestamp": ai_info.get("processing_timestamp"),
        "processing_status": ai_info.get("processing_status", ai_info.get("status", "FAILED")),
        "input_image": Path(image_path).name,
    }
    result["topology_stats"] = topology_stats

    if ground_truth_path:
        result["evaluation"] = evaluate_against_ground_truth(result["parcels"], ground_truth_path)
    else:
        result["evaluation"] = {"available": False}

    return result
