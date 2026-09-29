from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, HTTPException, UploadFile
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
