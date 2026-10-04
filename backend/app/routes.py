from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from .auth import get_current_auth
from .services.analysis import analyze_image
from .services.export_service import to_json_bytes
from .services.storage import AnalysisStore
from .services.supabase_client import supabase_rest

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


def _load_analysis_or_404(analysis_id: str):
    result = ANALYSES.get(analysis_id) or STORE.load(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return result


def _verify_survey_access(survey_id: str, access_token: str):
    rows = supabase_rest(
        "GET",
        "surveys",
        access_token,
        params={"select": "id,project_id,name,status", "id": f"eq.{survey_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Survey not found or access denied.")
    return rows[0]


def _update_job(job_id: str, access_token: str, payload: dict):
    return supabase_rest(
        "PATCH",
        "processing_jobs",
        access_token,
        params={"id": f"eq.{job_id}"},
        json=payload,
        prefer="return=minimal",
    )


def _persist_analysis(result: dict, *, analysis_id: str, survey_id: str, access_token: str, job_id: str):
    features = result.get("parcels", {}).get("features", [])
    rows = []

    for feature in features:
        props = feature.get("properties") or {}
        parcel_id = str(props.get("parcel_id") or props.get("id") or uuid4().hex[:12])
        rows.append({
            "survey_id": survey_id,
            "parcel_id": parcel_id,
            "area_sq_m": props.get("area_sq_m"),
            "perimeter_m": props.get("perimeter_m") or props.get("parcel_perimeter"),
            "review_score": props.get("review_score"),
            "review_priority": props.get("review_priority"),
            "status": props.get("review_status") or props.get("status") or "candidate",
            "geometry_crs": "LOCAL_IMAGE_0_100",
            "geom_crs": None,
            "ai_evidence": {
                "boundary_evidence": props.get("boundary_evidence"),
                "ai_evidence": props.get("ai_evidence"),
                "model_provider": props.get("model_provider"),
                "model_version": props.get("model_version"),
                "confidence": props.get("confidence"),
                "confidence_available": props.get("confidence_available", False),
            },
            "reference_comparison": {
                "reference_area": props.get("reference_area"),
                "percentage_area_difference": props.get("percentage_area_difference"),
                "reference_iou": props.get("reference_iou"),
                "boundary_displacement": props.get("boundary_displacement"),
                "discrepancy_status": props.get("discrepancy_status"),
            },
            "provenance": {
                "analysis_id": analysis_id,
                "processing_job_id": job_id,
                "source": props.get("source") or "SahiNaksha analysis pipeline",
                "cadastral_mode": result.get("cadastral_mode"),
                "analysis_mode": result.get("analysis_mode"),
                "ai_engine": result.get("ai_engine"),
                "geometry_coordinate_space": "image-local normalized 0..100",
            },
            "properties": props,
        })

    inserted = supabase_rest(
        "POST",
        "parcels",
        access_token,
        params={"on_conflict": "survey_id,parcel_id"},
        json=rows,
        prefer="resolution=merge-duplicates,return=representation",
    ) if rows else []

    by_parcel = {str(row["parcel_id"]): row["id"] for row in (inserted or [])}
    for feature in features:
        props = feature.get("properties") or {}
        parcel_id = str(props.get("parcel_id") or props.get("id") or "")
        db_id = by_parcel.get(parcel_id)
        geometry = feature.get("geometry")
        if db_id and geometry:
            supabase_rest(
                "POST",
                "rpc/set_parcel_native_geometry",
                access_token,
                json={"p_parcel_id": db_id, "p_geometry": geometry, "p_srid": 0},
            )

    issues = result.get("validation", {}).get("issues", [])
    if issues:
        supabase_rest(
            "POST",
            "validation_issues",
            access_token,
            json=[{
                "survey_id": survey_id,
                "parcel_id": issue.get("parcel_id"),
                "issue_type": issue.get("issue_type", "UNKNOWN"),
                "severity": issue.get("severity", "WARNING"),
                "description": issue.get("description", ""),
                "evidence": issue.get("evidence") or {},
                "status": issue.get("status", "OPEN"),
                "resolved": str(issue.get("status", "OPEN")).upper() in {"RESOLVED", "CLOSED"},
            } for issue in issues],
            prefer="return=minimal",
        )


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    survey_id: str = Form(...),
    reference_parcels: UploadFile | None = File(None),
    ground_truth: UploadFile | None = File(None),
    dsm: UploadFile | None = File(None),
    auth=Depends(get_current_auth),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, JPEG and PNG images are supported.")

    access_token = auth["access_token"]
    survey = _verify_survey_access(survey_id, access_token)
    if str(survey["project_id"]) != str(project_id):
        raise HTTPException(status_code=403, detail="Project does not own the selected survey.")

    uploads = Path(__file__).resolve().parents[1] / "uploads"
    uploads.mkdir(exist_ok=True)
    image_path = await _save_upload(file, uploads, {".jpg", ".jpeg", ".png"})
    reference_path = await _save_upload(reference_parcels, uploads, {".json", ".geojson"}) if reference_parcels else None
    ground_truth_path = await _save_upload(ground_truth, uploads, {".json", ".geojson"}) if ground_truth else None
    dsm_path = await _save_upload(dsm, uploads, {".jpg", ".jpeg", ".png"}) if dsm else None

    analysis_id = uuid4().hex
    job_rows = supabase_rest(
        "POST",
        "processing_jobs",
        access_token,
        json={
            "survey_id": survey_id,
            "created_by": auth["id"],
            "analysis_id": analysis_id,
            "status": "running",
            "progress": 10,
            "stage": "Processing",
        },
        prefer="return=representation",
    )
    job_id = job_rows[0]["id"]

    try:
        result = analyze_image(
            str(image_path),
            str(reference_path) if reference_path else None,
            str(ground_truth_path) if ground_truth_path else None,
            str(dsm_path) if dsm_path else None,
        )
        payload = {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "survey_id": survey_id,
            "processing_job_id": job_id,
            "status": "completed",
            "original_image_url": f"/uploads/{image_path.name}",
            **result,
        }

        _persist_analysis(
            result,
            analysis_id=analysis_id,
            survey_id=survey_id,
            access_token=access_token,
            job_id=job_id,
        )
        _update_job(job_id, access_token, {
            "status": "completed",
            "progress": 100,
            "stage": "Complete",
            "result_snapshot": payload,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        supabase_rest(
            "PATCH",
            "surveys",
            access_token,
            params={"id": f"eq.{survey_id}"},
            json={"status": "complete", "source_crs": result.get("raster_metadata", {}).get("crs"), "source_image_url": payload["original_image_url"]},
            prefer="return=minimal",
        )

        ANALYSES[analysis_id] = payload
        STORE.save(analysis_id, payload)
        return payload
    except ValueError as exc:
        _update_job(job_id, access_token, {"status": "failed", "stage": "Validation failed", "error_message": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        _update_job(job_id, access_token, {"status": "failed", "stage": "Processing failed", "error_message": str(exc)})
        raise HTTPException(status_code=500, detail=f"Analysis persistence/pipeline failed: {exc}") from exc


def _authorized_result(analysis_id: str, auth):
    result = _load_analysis_or_404(analysis_id)
    survey_id = result.get("survey_id")
    if not survey_id:
        raise HTTPException(status_code=403, detail="Analysis is not linked to an authenticated survey.")
    _verify_survey_access(survey_id, auth["access_token"])
    return result


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, auth=Depends(get_current_auth)):
    return _authorized_result(analysis_id, auth)


@router.get("/analysis/{analysis_id}/metrics")
def get_analysis_metrics(analysis_id: str, auth=Depends(get_current_auth)):
    result = _authorized_result(analysis_id, auth)
    parcels = result.get("parcels", {})
    features = parcels.get("features", [])
    review_scores = [f.get("properties", {}).get("review_score") for f in features if isinstance(f.get("properties", {}).get("review_score"), (int, float))]
    area_sq_m = [f.get("properties", {}).get("area_sq_m") for f in features if isinstance(f.get("properties", {}).get("area_sq_m"), (int, float))]
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


@router.get("/analysis/{analysis_id}/export")
def export_analysis(analysis_id: str, auth=Depends(get_current_auth)):
    result = _authorized_result(analysis_id, auth)
    data = to_json_bytes(result)
    supabase_rest(
        "POST",
        "exports",
        auth["access_token"],
        json={
            "survey_id": result["survey_id"],
            "processing_job_id": result.get("processing_job_id"),
            "created_by": auth["id"],
            "format": "geojson",
            "status": "generated",
            "file_name": f"sahinaksha-{analysis_id}.geojson",
            "metadata": {"analysis_id": analysis_id, "source": "FastAPI analysis export"},
        },
        prefer="return=minimal",
    )
    return Response(content=data, media_type="application/geo+json", headers={"Content-Disposition": f'attachment; filename="sahinaksha-{analysis_id}.geojson"'})


@router.get("/analysis/{analysis_id}/validation")
def get_validation_results(
    analysis_id: str,
    severity: str | None = Query(None),
    issue_type: str | None = Query(None),
    status: str | None = Query(None),
    parcel_id: str | None = Query(None),
    auth=Depends(get_current_auth),
):
    result = _authorized_result(analysis_id, auth)
    issues = list(result.get("validation", {}).get("issues", []))
    if severity:
        issues = [i for i in issues if str(i.get("severity", "")).upper() == severity.upper()]
    if issue_type:
        issues = [i for i in issues if str(i.get("issue_type", "")).upper() == issue_type.upper()]
    if status:
        issues = [i for i in issues if str(i.get("status", "")).upper() == status.upper()]
    if parcel_id:
        issues = [i for i in issues if str(i.get("parcel_id", "")) == str(parcel_id)]
    return {
        "analysis_id": analysis_id,
        "issue_count": len(issues),
        "filters": {"severity": severity, "issue_type": issue_type, "status": status, "parcel_id": parcel_id},
        "severity_counts": {level: sum(1 for issue in issues if str(issue.get("severity", "")).upper() == level) for level in ("INFO", "WARNING", "ERROR", "CRITICAL")},
        "issues": issues,
    }


@router.get("/analysis/{analysis_id}/validation/summary")
def get_validation_summary(analysis_id: str, auth=Depends(get_current_auth)):
    result = _authorized_result(analysis_id, auth)
    validation = result.get("validation", {})
    review_summary = result.get("parcels", {}).get("review_summary", {})
    return {
        "analysis_id": analysis_id,
        "parcel_count": len(result.get("parcels", {}).get("features", [])),
        "issue_count": validation.get("issue_count", len(validation.get("issues", []))),
        "severity_counts": validation.get("severity_counts", {}),
        "status_counts": validation.get("status_counts", {}),
        "review_priority_counts": review_summary.get("priority_counts", {}),
        "high_priority_count": review_summary.get("high_priority_count", 0),
        "mean_review_score": review_summary.get("mean_review_score"),
        "score_definition": review_summary.get("score_definition", "Deterministic review-risk indicator for surveyor triage; not AI accuracy or probability."),
    }


@router.get("/analysis/{analysis_id}/validation/parcels/{parcel_id}")
def get_parcel_validation(analysis_id: str, parcel_id: str, auth=Depends(get_current_auth)):
    result = _authorized_result(analysis_id, auth)
    parcel = next((f for f in result.get("parcels", {}).get("features", []) if str(f.get("properties", {}).get("parcel_id")) == str(parcel_id)), None)
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found.")
    issues = [i for i in result.get("validation", {}).get("issues", []) if str(i.get("parcel_id")) == str(parcel_id)]
    props = parcel.get("properties", {})
    return {
        "analysis_id": analysis_id,
        "parcel_id": parcel_id,
        "validation": {"status": props.get("validation_status", "PASS"), "geometry_valid": props.get("geometry_valid"), "issue_count": len(issues), "issues": issues},
        "review": {"priority": props.get("review_priority", "LOW"), "score": props.get("review_score"), "reasons": props.get("review_reasons", []), "evidence": props.get("review_evidence", []), "score_definition": props.get("score_definition", "Deterministic review-risk indicator for surveyor triage; not AI accuracy or probability.")},
        "action": "Surveyor Review Required" if props.get("review_required") else "No additional review flag",
    }


@router.get("/surveys/{survey_id}/latest-result")
def get_latest_survey_result(survey_id: str, auth=Depends(get_current_auth)):
    _verify_survey_access(survey_id, auth["access_token"])
    rows = supabase_rest(
        "GET",
        "processing_jobs",
        auth["access_token"],
        params={"select": "id,analysis_id,status,result_snapshot,created_at,completed_at", "survey_id": f"eq.{survey_id}", "status": "eq.completed", "order": "created_at.desc", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No completed processing result exists for this survey.")
    return rows[0]
