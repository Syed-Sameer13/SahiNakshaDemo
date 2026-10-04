from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from urllib.parse import urlparse
import csv
import html
import io
import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .auth import get_current_auth
from .services.analysis import analyze_image
from .services.export_service import to_json_bytes
from .services.storage import AnalysisStore
from .services.supabase_client import supabase_rest

router = APIRouter()
ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_SIZE = 20 * 1024 * 1024
ANALYSES = {}
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOADS = BASE_DIR / "uploads"
STORE = AnalysisStore(BASE_DIR / "outputs" / "analyses")


class ErrorResponse(BaseModel):
    error: dict


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class SurveyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ParcelPatch(BaseModel):
    parcel_id: str | None = None
    area_sq_m: float | None = None
    perimeter_m: float | None = None
    review_score: float | None = None
    review_priority: str | None = None
    status: str | None = None
    properties: dict | None = None
    geometry: dict | None = None
    geometry_crs: str | None = None


class ParcelVerify(BaseModel):
    decision: str = Field(pattern="^(ACCEPT|NEEDS_REVIEW|REJECT|REQUEST_FIELD_VERIFICATION)$")
    comments: str | None = None
    geometry: dict | None = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _error(code: str, message: str, details: dict | None = None, http_status: int = 400):
    raise HTTPException(status_code=http_status, detail={"error": {"code": code, "message": message, "details": details or {}}})


async def _save_upload(upload: UploadFile, directory: Path, allowed_suffixes):
    content = await upload.read()
    if not content:
        _error("EMPTY_FILE", f"{upload.filename or 'Uploaded file'} is empty.")
    if len(content) > MAX_SIZE:
        _error("FILE_TOO_LARGE", "Uploaded file exceeds the 20 MB prototype limit.")
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed_suffixes:
        _error("UNSUPPORTED_FILE", f"Unsupported file type: {suffix}", {"allowed": sorted(allowed_suffixes)})
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}{suffix}"
    path.write_bytes(content)
    return path


def _verify_project_access(project_id: str, access_token: str):
    rows = supabase_rest("GET", "projects", access_token, params={"select": "*", "id": f"eq.{project_id}", "limit": "1"})
    if not rows:
        _error("PROJECT_NOT_FOUND", "Project not found or access denied.", http_status=404)
    return rows[0]


def _verify_survey_access(survey_id: str, access_token: str):
    rows = supabase_rest("GET", "surveys", access_token, params={"select": "*", "id": f"eq.{survey_id}", "limit": "1"})
    if not rows:
        _error("SURVEY_NOT_FOUND", "Survey not found or access denied.", http_status=404)
    return rows[0]


def _get_parcel(parcel_id: str, access_token: str):
    rows = supabase_rest("GET", "parcels", access_token, params={"select": "*", "id": f"eq.{parcel_id}", "limit": "1"})
    if not rows:
        _error("PARCEL_NOT_FOUND", "Parcel not found or access denied.", http_status=404)
    parcel = rows[0]
    _verify_survey_access(str(parcel["survey_id"]), access_token)
    return parcel


def _update_job(job_id: str, access_token: str, payload: dict):
    return supabase_rest("PATCH", "processing_jobs", access_token, params={"id": f"eq.{job_id}"}, json=payload, prefer="return=minimal")


def _job_status(job_id: str, access_token: str):
    rows = supabase_rest("GET", "processing_jobs", access_token, params={"select": "*", "id": f"eq.{job_id}", "limit": "1"})
    if not rows:
        _error("JOB_NOT_FOUND", "Processing job not found.", http_status=404)
    return rows[0]


def _latest_job(survey_id: str, access_token: str, completed_only=False):
    params = {
        "select": "*",
        "survey_id": f"eq.{survey_id}",
        "order": "created_at.desc",
        "limit": "1",
    }
    if completed_only:
        params["status"] = "eq.COMPLETED"
    rows = supabase_rest("GET", "processing_jobs", access_token, params=params)
    return rows[0] if rows else None


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
    inserted = supabase_rest("POST", "parcels", access_token, params={"on_conflict": "survey_id,parcel_id"}, json=rows, prefer="resolution=merge-duplicates,return=representation") if rows else []
    by_parcel = {str(row["parcel_id"]): row["id"] for row in (inserted or [])}
    for feature in features:
        props = feature.get("properties") or {}
        db_id = by_parcel.get(str(props.get("parcel_id") or props.get("id") or ""))
        if db_id and feature.get("geometry"):
            supabase_rest("POST", "rpc/set_parcel_native_geometry", access_token, json={"p_parcel_id": db_id, "p_geometry": feature["geometry"], "p_srid": 0})
    issues = result.get("validation", {}).get("issues", [])
    if issues:
        supabase_rest("POST", "validation_issues", access_token, json=[{
            "survey_id": survey_id,
            "parcel_id": issue.get("parcel_id"),
            "issue_type": issue.get("issue_type", "UNKNOWN"),
            "severity": issue.get("severity", "WARNING"),
            "description": issue.get("description", ""),
            "evidence": issue.get("evidence") or {},
            "status": issue.get("status", "OPEN"),
            "resolved": str(issue.get("status", "OPEN")).upper() in {"RESOLVED", "CLOSED"},
        } for issue in issues], prefer="return=minimal")


def _run_processing(job_id: str, survey_id: str, access_token: str, analysis_id: str, image_path: str, reference_path: str | None, ground_truth_path: str | None, dsm_path: str | None, project_id: str):
    started = _now()
    try:
        _update_job(job_id, access_token, {"status": "PROCESSING", "stage": "AI/GIS analysis", "started_at": started, "progress": 0})
        result = analyze_image(image_path, reference_path, ground_truth_path, dsm_path)
        model = result.get("ai_engine", {}).get("model_name") or result.get("ai_engine", {}).get("provider") or result.get("analysis_mode") or "unknown"
        payload = {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "survey_id": survey_id,
            "processing_job_id": job_id,
            "status": "COMPLETED",
            "original_image_url": f"/uploads/surveys/{survey_id}/{Path(image_path).name}",
            **result,
        }
        _persist_analysis(result, analysis_id=analysis_id, survey_id=survey_id, access_token=access_token, job_id=job_id)
        ANALYSES[analysis_id] = payload
        STORE.save(analysis_id, payload)
        _update_job(job_id, access_token, {
            "status": "COMPLETED",
            "stage": "Complete",
            "progress": 100,
            "model_used": str(model),
            "output": {"analysis_id": analysis_id, "parcel_count": len(result.get("parcels", {}).get("features", [])), "ai_status": result.get("ai_status")},
            "result_snapshot": payload,
            "completed_at": _now(),
            "error_message": None,
        })
        supabase_rest("PATCH", "surveys", access_token, params={"id": f"eq.{survey_id}"}, json={"status": "complete", "source_crs": result.get("raster_metadata", {}).get("crs"), "source_image_url": payload["original_image_url"]}, prefer="return=minimal")
    except Exception as exc:
        _update_job(job_id, access_token, {"status": "FAILED", "stage": "Processing failed", "error_message": str(exc), "completed_at": _now()})
        try:
            supabase_rest("PATCH", "surveys", access_token, params={"id": f"eq.{survey_id}"}, json={"status": "failed"}, prefer="return=minimal")
        except Exception:
            pass


@router.get("/api/health")
def api_health():
    return {"status": "ok", "service": "SahiNaksha API", "version": "0.5.0"}


@router.get("/api/projects")
def list_projects(auth=Depends(get_current_auth)):
    return supabase_rest("GET", "projects", auth["access_token"], params={"select": "*", "order": "created_at.desc"})


@router.post("/api/projects", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, auth=Depends(get_current_auth)):
    rows = supabase_rest("POST", "projects", auth["access_token"], json={"owner_id": auth["id"], "name": body.name.strip(), "description": body.description}, prefer="return=representation")
    return rows[0]


@router.get("/api/projects/{project_id}")
def get_project(project_id: str, auth=Depends(get_current_auth)):
    return _verify_project_access(project_id, auth["access_token"])


@router.patch("/api/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch, auth=Depends(get_current_auth)):
    _verify_project_access(project_id, auth["access_token"])
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if not changes:
        _error("NO_CHANGES", "No project fields were provided.")
    rows = supabase_rest("PATCH", "projects", auth["access_token"], params={"id": f"eq.{project_id}"}, json=changes, prefer="return=representation")
    return rows[0] if rows else _verify_project_access(project_id, auth["access_token"])


@router.get("/api/projects/{project_id}/surveys")
def list_surveys(project_id: str, auth=Depends(get_current_auth)):
    _verify_project_access(project_id, auth["access_token"])
    return supabase_rest("GET", "surveys", auth["access_token"], params={"select": "*", "project_id": f"eq.{project_id}", "order": "created_at.desc"})


@router.post("/api/projects/{project_id}/surveys", status_code=status.HTTP_201_CREATED)
def create_survey(project_id: str, body: SurveyCreate, auth=Depends(get_current_auth)):
    _verify_project_access(project_id, auth["access_token"])
    rows = supabase_rest("POST", "surveys", auth["access_token"], json={"project_id": project_id, "name": body.name.strip(), "status": "created"}, prefer="return=representation")
    return rows[0]


@router.get("/api/surveys/{survey_id}")
def get_survey(survey_id: str, auth=Depends(get_current_auth)):
    survey = _verify_survey_access(survey_id, auth["access_token"])
    jobs = supabase_rest("GET", "processing_jobs", auth["access_token"], params={"select":"id,status,progress,stage,error_message,model_used,started_at,completed_at,created_at","survey_id":f"eq.{survey_id}","order":"created_at.desc","limit":"5"})
    return {**survey, "processing_jobs": jobs}


@router.post("/api/surveys/{survey_id}/upload")
async def upload_survey(survey_id: str, file: UploadFile = File(...), reference_parcels: UploadFile | None = File(None), ground_truth: UploadFile | None = File(None), dsm: UploadFile | None = File(None), auth=Depends(get_current_auth)):
    _verify_survey_access(survey_id, auth["access_token"])
    directory = UPLOADS / "surveys" / survey_id
    if file.content_type not in ALLOWED_TYPES:
        _error("UNSUPPORTED_FILE", "Only JPG, JPEG and PNG orthomosaic images are supported.")
    image_path = await _save_upload(file, directory, {".jpg", ".jpeg", ".png"})
    optional = {}
    if reference_parcels:
        optional["reference"] = await _save_upload(reference_parcels, directory, {".json", ".geojson"})
    if ground_truth:
        optional["ground_truth"] = await _save_upload(ground_truth, directory, {".json", ".geojson"})
    if dsm:
        optional["dsm"] = await _save_upload(dsm, directory, {".jpg", ".jpeg", ".png"})
    # Keep stable manifest names so a later /process call can discover the uploaded inputs.
    for key, path in optional.items():
        target = directory / f"{key}{path.suffix}"
        path.replace(target)
        optional[key] = target
    source_url = f"/uploads/surveys/{survey_id}/{image_path.name}"
    supabase_rest("PATCH", "surveys", auth["access_token"], params={"id": f"eq.{survey_id}"}, json={"status":"uploaded","source_image_url":source_url}, prefer="return=minimal")
    return {"survey_id": survey_id, "status": "uploaded", "source_image_url": source_url, "inputs": {"orthomosaic": image_path.name, **{k:v.name for k,v in optional.items()}}}


@router.post("/api/surveys/{survey_id}/process", status_code=status.HTTP_202_ACCEPTED)
def process_survey(survey_id: str, background_tasks: BackgroundTasks, auth=Depends(get_current_auth)):
    survey = _verify_survey_access(survey_id, auth["access_token"])
    existing = _latest_job(survey_id, auth["access_token"])
    if existing and existing.get("status") in {"QUEUED", "PROCESSING", "queued", "processing"}:
        _error("PROCESSING_ACTIVE", "A processing job is already active for this survey.", {"job_id": existing["id"]}, 409)
    source = survey.get("source_image_url")
    if not source:
        _error("NO_UPLOAD", "Upload an orthomosaic before starting processing.")
    image_path = UPLOADS / "surveys" / survey_id / Path(urlparse(source).path).name
    if not image_path.exists():
        _error("UPLOAD_MISSING", "The survey source image is not available on the backend filesystem.", http_status=404)
    directory = image_path.parent
    reference_path = next(iter(directory.glob("reference.*")), None)
    ground_truth_path = next(iter(directory.glob("ground_truth.*")), None)
    dsm_path = next(iter(directory.glob("dsm.*")), None)
    analysis_id = uuid4().hex
    input_meta = {"orthomosaic": image_path.name, "reference_parcels": reference_path.name if reference_path else None, "ground_truth": ground_truth_path.name if ground_truth_path else None, "dsm": dsm_path.name if dsm_path else None}
    rows = supabase_rest("POST", "processing_jobs", auth["access_token"], json={"survey_id":survey_id,"created_by":auth["id"],"analysis_id":analysis_id,"status":"QUEUED","progress":0,"stage":"Queued","input":input_meta}, prefer="return=representation")
    job = rows[0]
    supabase_rest("PATCH", "surveys", auth["access_token"], params={"id":f"eq.{survey_id}"}, json={"status":"processing"}, prefer="return=minimal")
    background_tasks.add_task(_run_processing, job["id"], survey_id, auth["access_token"], analysis_id, str(image_path), str(reference_path) if reference_path else None, str(ground_truth_path) if ground_truth_path else None, str(dsm_path) if dsm_path else None, str(survey["project_id"]))
    return {"job_id": job["id"], "analysis_id": analysis_id, "survey_id": survey_id, "status": "QUEUED", "message": "Processing accepted. Poll processing-status for the authoritative job state."}


@router.get("/api/surveys/{survey_id}/processing-status")
def processing_status(survey_id: str, auth=Depends(get_current_auth)):
    _verify_survey_access(survey_id, auth["access_token"])
    job = _latest_job(survey_id, auth["access_token"])
    if not job:
        _error("NO_PROCESSING_JOB", "No processing job exists for this survey.", http_status=404)
    return {"job_id": job["id"], "survey_id": survey_id, "status": job["status"], "progress": job.get("progress",0), "stage": job.get("stage"), "started_at": job.get("started_at"), "completed_at": job.get("completed_at"), "error": job.get("error_message"), "model_used": job.get("model_used"), "input": job.get("input") or {}, "output": job.get("output") or {}}


@router.get("/api/surveys/{survey_id}/results")
def survey_results(survey_id: str, auth=Depends(get_current_auth)):
    _verify_survey_access(survey_id, auth["access_token"])
    job = _latest_job(survey_id, auth["access_token"], completed_only=True)
    if not job or not job.get("result_snapshot"):
        _error("RESULT_NOT_READY", "No completed processing result exists for this survey.", http_status=404)
    return job["result_snapshot"]


@router.get("/api/surveys/{survey_id}/parcels")
def survey_parcels(survey_id: str, auth=Depends(get_current_auth)):
    _verify_survey_access(survey_id, auth["access_token"])
    rows = supabase_rest("GET", "parcels", auth["access_token"], params={"select":"id,survey_id,parcel_id,area_sq_m,perimeter_m,review_score,review_priority,status,geometry_crs,geom_crs,ai_evidence,reference_comparison,provenance,properties,reviewer,reviewed_at,updated_at","survey_id":f"eq.{survey_id}","order":"created_at.asc"})
    return {"survey_id": survey_id, "count": len(rows), "parcels": rows}


@router.get("/api/parcels/{parcel_id}")
def get_parcel(parcel_id: str, auth=Depends(get_current_auth)):
    return _get_parcel(parcel_id, auth["access_token"])


@router.patch("/api/parcels/{parcel_id}")
def patch_parcel(parcel_id: str, body: ParcelPatch, auth=Depends(get_current_auth)):
    parcel = _get_parcel(parcel_id, auth["access_token"])
    changes = body.model_dump(exclude_unset=True)
    geometry = changes.pop("geometry", None)
    properties = changes.get("properties")
    if properties is not None:
        changes["properties"] = {**(parcel.get("properties") or {}), **properties}
    if "geometry_crs" in changes and changes["geometry_crs"] is None:
        changes.pop("geometry_crs")
    if not changes and geometry is None:
        _error("NO_CHANGES", "No parcel fields were provided.")
    if changes:
        rows = supabase_rest("PATCH", "parcels", auth["access_token"], params={"id":f"eq.{parcel_id}"}, json=changes, prefer="return=representation")
        parcel = rows[0] if rows else _get_parcel(parcel_id, auth["access_token"])
    if geometry is not None:
        supabase_rest("POST", "rpc/set_parcel_native_geometry", auth["access_token"], json={"p_parcel_id":parcel_id,"p_geometry":geometry,"p_srid":0})
        parcel["properties"] = {**(parcel.get("properties") or {}), "edited_geometry": geometry}
    return parcel


def _verify_and_record(parcel_id: str, decision: str, comments: str | None, geometry: dict | None, auth):
    parcel = _get_parcel(parcel_id, auth["access_token"])
    status_map = {"ACCEPT":"Human Verified","NEEDS_REVIEW":"Needs Review","REJECT":"Rejected","REQUEST_FIELD_VERIFICATION":"Needs Field Survey"}
    new_status = status_map[decision]
    props = dict(parcel.get("properties") or {})
    if geometry is not None:
        supabase_rest("POST", "rpc/set_parcel_native_geometry", auth["access_token"], json={"p_parcel_id":parcel_id,"p_geometry":geometry,"p_srid":0})
        props["edited_geometry"] = geometry
    props["review_status"] = new_status
    if comments:
        props["reviewer_notes"] = comments
    now = _now()
    supabase_rest("PATCH","parcels",auth["access_token"],params={"id":f"eq.{parcel_id}"},json={"status":new_status,"properties":props,"reviewer":auth["id"],"reviewed_at":now,"updated_at":now},prefer="return=minimal")
    supabase_rest("POST","reviews",auth["access_token"],json={"survey_id":parcel["survey_id"],"parcel_record_id":parcel_id,"parcel_id":parcel["parcel_id"],"reviewer":auth["id"],"decision":decision,"comments":comments,"previous_status":parcel.get("status"),"new_status":new_status,"edited_geometry":geometry},prefer="return=minimal")
    return {"parcel_id":parcel_id,"survey_id":parcel["survey_id"],"decision":decision,"status":new_status,"reviewed_at":now,"message":"Review decision saved."}


@router.post("/api/parcels/{parcel_id}/verify")
def verify_parcel(parcel_id: str, body: ParcelVerify, auth=Depends(get_current_auth)):
    if body.decision == "REQUEST_FIELD_VERIFICATION":
        _error("INVALID_DECISION", "Use the dedicated request-field-verification endpoint for that action.")
    return _verify_and_record(parcel_id, body.decision, body.comments, body.geometry, auth)


@router.post("/api/parcels/{parcel_id}/request-field-verification")
def request_field_verification(parcel_id: str, body: ParcelVerify | None = None, auth=Depends(get_current_auth)):
    comments = body.comments if body else None
    geometry = body.geometry if body else None
    return _verify_and_record(parcel_id, "REQUEST_FIELD_VERIFICATION", comments, geometry, auth)


@router.get("/api/surveys/{survey_id}/validation")
def survey_validation(survey_id: str, severity: str | None = Query(None), issue_type: str | None = Query(None), status_filter: str | None = Query(None, alias="status"), parcel_id: str | None = Query(None), auth=Depends(get_current_auth)):
    _verify_survey_access(survey_id, auth["access_token"])
    params = {"select":"id,survey_id,parcel_id,issue_type,severity,description,evidence,status,resolved,created_at,updated_at","survey_id":f"eq.{survey_id}","order":"created_at.desc"}
    if severity: params["severity"] = f"eq.{severity.upper()}"
    if issue_type: params["issue_type"] = f"eq.{issue_type}"
    if status_filter: params["status"] = f"eq.{status_filter.upper()}"
    if parcel_id: params["parcel_id"] = f"eq.{parcel_id}"
    rows = supabase_rest("GET","validation_issues",auth["access_token"],params=params)
    return {"survey_id":survey_id,"count":len(rows),"issues":rows}


def _latest_snapshot_with_db_reviews(survey_id: str, auth):
    job = _latest_job(survey_id, auth["access_token"], completed_only=True)
    if not job or not job.get("result_snapshot"):
        _error("RESULT_NOT_READY","No completed processing result exists for this survey.",http_status=404)
    snapshot = json.loads(json.dumps(job["result_snapshot"]))
    db_parcels = supabase_rest("GET","parcels",auth["access_token"],params={"select":"parcel_id,status,properties,updated_at","survey_id":f"eq.{survey_id}"})
    by_id = {str(p["parcel_id"]):p for p in db_parcels}
    for feature in snapshot.get("parcels",{}).get("features",[]):
        pid = str((feature.get("properties") or {}).get("parcel_id") or "")
        db = by_id.get(pid)
        if db:
            feature["properties"] = {**(feature.get("properties") or {}), **(db.get("properties") or {}), "review_status": db.get("status"), "updated_at": db.get("updated_at")}
            if feature["properties"].get("edited_geometry"):
                feature["geometry"] = feature["properties"]["edited_geometry"]
    return snapshot, job


def _record_export(survey_id, job_id, fmt, auth, file_name):
    supabase_rest("POST","exports",auth["access_token"],json={"survey_id":survey_id,"processing_job_id":job_id,"created_by":auth["id"],"format":fmt,"status":"generated","file_name":file_name,"metadata":{"source":"persisted survey result"}},prefer="return=minimal")


@router.get("/api/surveys/{survey_id}/export/geojson")
def export_geojson(survey_id: str, auth=Depends(get_current_auth)):
    snapshot, job = _latest_snapshot_with_db_reviews(survey_id, auth)
    data = to_json_bytes(snapshot)
    filename = f"sahinaksha-{survey_id}.geojson"
    _record_export(survey_id, job["id"], "geojson", auth, filename)
    return Response(content=data, media_type="application/geo+json", headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/api/surveys/{survey_id}/export/csv")
def export_csv(survey_id: str, auth=Depends(get_current_auth)):
    snapshot, job = _latest_snapshot_with_db_reviews(survey_id, auth)
    output = io.StringIO()
    writer = csv.writer(output)
    fields = ["parcel_id","area_sq_m","perimeter_m","review_score","review_priority","status","validation_status","reference_iou","percentage_area_difference"]
    writer.writerow(fields)
    for feature in snapshot.get("parcels",{}).get("features",[]):
        p = feature.get("properties") or {}
        writer.writerow([p.get(k) for k in fields])
    filename = f"sahinaksha-{survey_id}.csv"
    _record_export(survey_id, job["id"], "csv", auth, filename)
    return Response(content=output.getvalue().encode("utf-8"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/api/surveys/{survey_id}/export/report")
def export_report(survey_id: str, auth=Depends(get_current_auth)):
    snapshot, job = _latest_snapshot_with_db_reviews(survey_id, auth)
    features = snapshot.get("parcels",{}).get("features",[])
    issues = snapshot.get("validation",{}).get("issues",[])
    html_body = f"""<!doctype html><html><head><meta charset="utf-8"><title>SahiNaksha Survey Report</title><style>body{{font-family:Arial,sans-serif;margin:40px;color:#172033}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd3dc;padding:8px;text-align:left}}th{{background:#eef2f6}}</style></head><body><h1>SahiNaksha Survey Report</h1><p><b>Survey:</b> {html.escape(survey_id)}</p><p><b>Processing job:</b> {html.escape(str(job["id"]))}</p><p><b>Parcels:</b> {len(features)} &nbsp; <b>Validation issues:</b> {len(issues)}</p><p><b>Legal status:</b> Preliminary AI/GIS evidence requiring human surveyor review. This output is not a legally authoritative cadastral boundary.</p><table><tr><th>Parcel</th><th>Area m²</th><th>Review priority</th><th>Status</th></tr>{''.join(f"<tr><td>{html.escape(str((f.get('properties') or {}).get('parcel_id','')))}</td><td>{html.escape(str((f.get('properties') or {}).get('area_sq_m','—')))}</td><td>{html.escape(str((f.get('properties') or {}).get('review_priority','LOW')))}</td><td>{html.escape(str((f.get('properties') or {}).get('review_status','candidate')))}</td></tr>" for f in features)}</table></body></html>"""
    filename = f"sahinaksha-{survey_id}-report.html"
    _record_export(survey_id, job["id"], "report", auth, filename)
    return Response(content=html_body, media_type="text/html; charset=utf-8", headers={"Content-Disposition":f'attachment; filename="{filename}"'})


# Legacy endpoints retained for the current frontend and existing integrations.
@router.post("/analyze")
async def analyze(file: UploadFile = File(...), project_id: str = Form(...), survey_id: str = Form(...), reference_parcels: UploadFile | None = File(None), ground_truth: UploadFile | None = File(None), dsm: UploadFile | None = File(None), auth=Depends(get_current_auth)):
    if file.content_type not in ALLOWED_TYPES:
        _error("UNSUPPORTED_FILE","Only JPG, JPEG and PNG images are supported.")
    survey = _verify_survey_access(survey_id, auth["access_token"])
    if str(survey["project_id"]) != str(project_id):
        _error("PROJECT_SURVEY_MISMATCH","Project does not own the selected survey.",http_status=403)
    uploads = UPLOADS / "surveys" / survey_id
    image_path = await _save_upload(file, uploads, {".jpg",".jpeg",".png"})
    reference_path = await _save_upload(reference_parcels, uploads, {".json",".geojson"}) if reference_parcels else None
    ground_truth_path = await _save_upload(ground_truth, uploads, {".json",".geojson"}) if ground_truth else None
    dsm_path = await _save_upload(dsm, uploads, {".jpg",".jpeg",".png"}) if dsm else None
    analysis_id = uuid4().hex
    rows = supabase_rest("POST","processing_jobs",auth["access_token"],json={"survey_id":survey_id,"created_by":auth["id"],"analysis_id":analysis_id,"status":"PROCESSING","progress":0,"stage":"AI/GIS analysis","input":{"orthomosaic":image_path.name}},prefer="return=representation")
    job_id = rows[0]["id"]
    try:
        result = analyze_image(str(image_path),str(reference_path) if reference_path else None,str(ground_truth_path) if ground_truth_path else None,str(dsm_path) if dsm_path else None)
        payload={"analysis_id":analysis_id,"project_id":project_id,"survey_id":survey_id,"processing_job_id":job_id,"status":"COMPLETED","original_image_url":f"/uploads/surveys/{survey_id}/{image_path.name}",**result}
        _persist_analysis(result,analysis_id=analysis_id,survey_id=survey_id,access_token=auth["access_token"],job_id=job_id)
        ANALYSES[analysis_id]=payload; STORE.save(analysis_id,payload)
        model=result.get("ai_engine",{}).get("model_name") or result.get("ai_engine",{}).get("provider") or result.get("analysis_mode") or "unknown"
        _update_job(job_id,auth["access_token"],{"status":"COMPLETED","progress":100,"stage":"Complete","model_used":str(model),"output":{"analysis_id":analysis_id,"parcel_count":len(result.get("parcels",{}).get("features",[]))},"result_snapshot":payload,"completed_at":_now(),"error_message":None})
        supabase_rest("PATCH","surveys",auth["access_token"],params={"id":f"eq.{survey_id}"},json={"status":"complete","source_image_url":payload["original_image_url"]},prefer="return=minimal")
        return payload
    except ValueError as exc:
        _update_job(job_id,auth["access_token"],{"status":"FAILED","error_message":str(exc),"completed_at":_now()})
        _error("PROCESSING_VALIDATION_FAILED",str(exc),http_status=400)
    except Exception as exc:
        _update_job(job_id,auth["access_token"],{"status":"FAILED","error_message":str(exc),"completed_at":_now()})
        _error("PROCESSING_FAILED",f"Analysis persistence/pipeline failed: {exc}",http_status=500)


def _authorized_result(analysis_id: str, auth):
    result = ANALYSES.get(analysis_id) or STORE.load(analysis_id)
    if not result:
        _error("ANALYSIS_NOT_FOUND","Analysis not found.",http_status=404)
    _verify_survey_access(str(result.get("survey_id")),auth["access_token"])
    return result


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, auth=Depends(get_current_auth)):
    return _authorized_result(analysis_id, auth)


@router.get("/analysis/{analysis_id}/metrics")
def get_analysis_metrics(analysis_id: str, auth=Depends(get_current_auth)):
    result=_authorized_result(analysis_id,auth)
    features=result.get("parcels",{}).get("features",[])
    scores=[f.get("properties",{}).get("review_score") for f in features if isinstance(f.get("properties",{}).get("review_score"),(int,float))]
    areas=[f.get("properties",{}).get("area_sq_m") for f in features if isinstance(f.get("properties",{}).get("area_sq_m"),(int,float))]
    return {"analysis_id":analysis_id,"analysis_mode":result.get("analysis_mode"),"ai_engine":result.get("ai_engine"),"cadastral_mode":result.get("cadastral_mode"),"topology":result.get("topology_stats",{}),"validation":result.get("validation",{}),"parcel_count":len(features),"mean_review_score":round(sum(scores)/len(scores),1) if scores else None,"total_area_sq_m":round(sum(areas),3) if areas else None,"area_sq_m_available":bool(areas),"area_summary":result.get("parcels",{}).get("area_summary",{}),"review_summary":result.get("parcels",{}).get("review_summary",{}),"evaluation":result.get("evaluation",{"available":False})}


@router.get("/analysis/{analysis_id}/export")
def export_analysis(analysis_id: str, auth=Depends(get_current_auth)):
    result=_authorized_result(analysis_id,auth)
    data=to_json_bytes(result)
    filename=f"sahinaksha-{analysis_id}.geojson"
    _record_export(result["survey_id"],result.get("processing_job_id"),"geojson",auth,filename)
    return Response(content=data,media_type="application/geo+json",headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/analysis/{analysis_id}/validation")
def get_validation_results(analysis_id: str, severity: str|None=Query(None), issue_type: str|None=Query(None), status_filter: str|None=Query(None,alias="status"), parcel_id: str|None=Query(None), auth=Depends(get_current_auth)):
    result=_authorized_result(analysis_id,auth)
    issues=list(result.get("validation",{}).get("issues",[]))
    if severity: issues=[i for i in issues if str(i.get("severity","")).upper()==severity.upper()]
    if issue_type: issues=[i for i in issues if str(i.get("issue_type","")).upper()==issue_type.upper()]
    if status_filter: issues=[i for i in issues if str(i.get("status","")).upper()==status_filter.upper()]
    if parcel_id: issues=[i for i in issues if str(i.get("parcel_id",""))==str(parcel_id)]
    return {"analysis_id":analysis_id,"issue_count":len(issues),"filters":{"severity":severity,"issue_type":issue_type,"status":status_filter,"parcel_id":parcel_id},"severity_counts":{level:sum(1 for issue in issues if str(issue.get("severity","")).upper()==level) for level in ("INFO","WARNING","ERROR","CRITICAL")},"issues":issues}


@router.get("/surveys/{survey_id}/latest-result")
def get_latest_survey_result(survey_id: str, auth=Depends(get_current_auth)):
    _verify_survey_access(survey_id,auth["access_token"])
    job=_latest_job(survey_id,auth["access_token"],completed_only=True)
    if not job: _error("RESULT_NOT_READY","No completed processing result exists for this survey.",http_status=404)
    return job
