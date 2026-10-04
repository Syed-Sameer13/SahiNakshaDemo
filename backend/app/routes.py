from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from .services.analysis import analyze_image
from .services.export_service import to_json_bytes
from .services.storage import AnalysisStore

router = APIRouter()
ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_SIZE = 20 * 1024 * 1024
ANALYSES = {}
STORE = AnalysisStore(Path(__file__).resolve().parents[1] / "outputs" / "analyses")


async def _save_upload(upload: UploadFile, directory: Path, allowed_suffixes):
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{upload.filename or 'Uploaded file'} is empty.")
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Uploaded file exceeds the 20 MB prototype limit.")
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
    path = directory / f"{uuid4().hex}{suffix}"
    path.write_bytes(content)
    return path


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    reference_parcels: UploadFile | None = File(None),
    ground_truth: UploadFile | None = File(None),
    dsm: UploadFile | None = File(None),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, JPEG and PNG images are supported.")

    uploads = Path(__file__).resolve().parents[1] / "uploads"
    uploads.mkdir(exist_ok=True)

    image_path = await _save_upload(file, uploads, {".jpg", ".jpeg", ".png"})
    reference_path = await _save_upload(reference_parcels, uploads, {".json", ".geojson"}) if reference_parcels else None
    ground_truth_path = await _save_upload(ground_truth, uploads, {".json", ".geojson"}) if ground_truth else None
    dsm_path = await _save_upload(dsm, uploads, {".jpg", ".jpeg", ".png"}) if dsm else None

    analysis_id = uuid4().hex
    try:
        result = analyze_image(
            str(image_path),
            str(reference_path) if reference_path else None,
            str(ground_truth_path) if ground_truth_path else None,
            str(dsm_path) if dsm_path else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis pipeline failed: {exc}")

    payload = {
        "analysis_id": analysis_id,
        "status": "completed",
        "original_image_url": f"/uploads/{image_path.name}",
        **result,
    }
    ANALYSES[analysis_id] = payload
    STORE.save(analysis_id, payload)
    return payload


@router.get("/analysis/{analysis_id}/export")
def export_analysis(analysis_id: str):
    result = ANALYSES.get(analysis_id) or STORE.load(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found. Run the analysis again before exporting.")
    return Response(
        content=to_json_bytes(result),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="sahinaksha-{analysis_id}.geojson"'},
    )

 
@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str):
    result = ANALYSES.get(analysis_id) or STORE.load(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return result


@router.get("/analysis/{analysis_id}/metrics")
def get_analysis_metrics(analysis_id: str):
    result = ANALYSES.get(analysis_id) or STORE.load(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    parcels = result.get("parcels", {})
    features = parcels.get("features", [])
    review_scores = [
        f.get("properties", {}).get("review_score")
        for f in features
        if isinstance(f.get("properties", {}).get("review_score"), (int, float))
    ]
    area_sq_m = [
        f.get("properties", {}).get("area_sq_m")
        for f in features
        if isinstance(f.get("properties", {}).get("area_sq_m"), (int, float))
    ]
    return {
        "analysis_id": analysis_id,
        "analysis_mode": result.get("analysis_mode"),
        "ai_engine": result.get("ai_engine"),
        "cadastral_mode": result.get("cadastral_mode"),
        "topology": result.get("topology_stats", {}),
        "validation": result.get("validation", {}),
        "parcel_count": len(features),
        "mean_review_score": round(sum(review_scores) / len(review_scores), 1) if review_scores else None,
        "total_area_sq_m": round(sum(area_sq_m), 3) if area_sq_m else None,
        "area_sq_m_available": bool(area_sq_m),
        "area_summary": parcels.get("area_summary", {}),
        "review_summary": parcels.get("review_summary", {}),
        "evaluation": result.get("evaluation", {"available": False}),
    }



def _load_analysis_or_404(analysis_id: str):
    result = ANALYSES.get(analysis_id) or STORE.load(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return result


@router.get("/analysis/{analysis_id}/validation")
def get_validation_results(
    analysis_id: str,
    severity: str | None = Query(None, description="INFO, WARNING, ERROR or CRITICAL"),
    issue_type: str | None = Query(None),
    status: str | None = Query(None),
    parcel_id: str | None = Query(None),
):
    """Return deterministic parcel validation issues with optional filters."""
    result = _load_analysis_or_404(analysis_id)
    validation = result.get("validation", {})
    issues = list(validation.get("issues", []))

    if severity:
        severity_value = severity.upper()
        issues = [i for i in issues if str(i.get("severity", "")).upper() == severity_value]
    if issue_type:
        issue_value = issue_type.upper()
        issues = [i for i in issues if str(i.get("issue_type", "")).upper() == issue_value]
    if status:
        status_value = status.upper()
        issues = [i for i in issues if str(i.get("status", "")).upper() == status_value]
    if parcel_id:
        issues = [i for i in issues if str(i.get("parcel_id", "")) == str(parcel_id)]

    return {
        "analysis_id": analysis_id,
        "issue_count": len(issues),
        "filters": {
            "severity": severity.upper() if severity else None,
            "issue_type": issue_type.upper() if issue_type else None,
            "status": status.upper() if status else None,
            "parcel_id": parcel_id,
        },
        "severity_counts": {
            level: sum(1 for issue in issues if issue.get("severity") == level)
            for level in ("INFO", "WARNING", "ERROR", "CRITICAL")
        },
        "issues": issues,
    }


@router.get("/analysis/{analysis_id}/validation/summary")
def get_validation_summary(analysis_id: str):
    """Return project-level validation and review-priority summary."""
    result = _load_analysis_or_404(analysis_id)
    validation = result.get("validation", {})
    parcels = result.get("parcels", {})
    review_summary = parcels.get("review_summary", {})

    return {
        "analysis_id": analysis_id,
        "parcel_count": len(parcels.get("features", [])),
        "issue_count": validation.get("issue_count", len(validation.get("issues", []))),
        "severity_counts": validation.get("severity_counts", {}),
        "status_counts": validation.get("status_counts", {}),
        "review_priority_counts": review_summary.get("priority_counts", {}),
        "high_priority_count": review_summary.get("high_priority_count", 0),
        "mean_review_score": review_summary.get("mean_review_score"),
        "score_definition": review_summary.get(
            "score_definition",
            "Deterministic review-risk indicator for surveyor triage; not AI accuracy or probability.",
        ),
    }


@router.get("/analysis/{analysis_id}/validation/parcels/{parcel_id}")
def get_parcel_validation(analysis_id: str, parcel_id: str):
    """Return one parcel's validation issues and explainable review priority."""
    result = _load_analysis_or_404(analysis_id)
    parcels = result.get("parcels", {}).get("features", [])
    parcel = next(
        (f for f in parcels if str(f.get("properties", {}).get("parcel_id")) == str(parcel_id)),
        None,
    )
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found.")

    issues = [
        issue for issue in result.get("validation", {}).get("issues", [])
        if str(issue.get("parcel_id")) == str(parcel_id)
    ]
    props = parcel.get("properties", {})
    return {
        "analysis_id": analysis_id,
        "parcel_id": parcel_id,
        "validation": {
            "status": props.get("validation_status", "PASS"),
            "geometry_valid": props.get("geometry_valid"),
            "issue_count": len(issues),
            "issues": issues,
        },
        "review": {
            "priority": props.get("review_priority", "LOW"),
            "score": props.get("review_score"),
            "reasons": props.get("review_reasons", []),
            "evidence": props.get("review_evidence", []),
            "score_definition": props.get(
                "score_definition",
                "Deterministic review-risk indicator for surveyor triage; not AI accuracy or probability.",
            ),
        },
        "action": "Surveyor Review Required" if props.get("review_required") else "No additional review flag",
    }
}
