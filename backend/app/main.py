import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .routes import router
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
MODEL_PATH = Path(os.getenv("SAHINAKSHA_PIXEL_MODEL_PATH", str(BASE_DIR / "models" / "sahinaksha_pixel_model.joblib")))
HOTOSM_MODEL_PATH = Path(os.getenv("SAHINAKSHA_HOTOSM_MODEL", str(BASE_DIR / "models" / "hotosm_dinov3s_buildings.onnx")))
YOLO_MODEL_PATH = Path(os.getenv("SAHINAKSHA_YOLO_MODEL", str(BASE_DIR / "models" / "sahinaksha_seg.pt")))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

configured_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()]
allow_origins = configured_origins or ["http://localhost:5173", "http://127.0.0.1:5173"]

app = FastAPI(title="SahiNaksha API", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.include_router(router)


def structured_error(code: str, message: str, details: dict | None = None):
    return {"error": {"code": code, "message": message, "details": details or {}}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        payload = detail
    else:
        payload = structured_error("HTTP_ERROR", str(detail), {})
    return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=structured_error("VALIDATION_ERROR", "Request validation failed.", {"errors": exc.errors()}),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=structured_error("INTERNAL_SERVER_ERROR", "An unexpected server error occurred.", {"type": type(exc).__name__}),
    )


@app.get("/")
def root():
    return {"name": "SahiNaksha API", "status": "running", "version": "0.5.0"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "SahiNaksha API",
        "version": "0.5.0",
        "ai_models": {
            "trained_pixel_model": MODEL_PATH.exists() and MODEL_PATH.stat().st_size >= 128,
            "hotosm_configured": HOTOSM_MODEL_PATH.exists(),
            "sam_configured": os.getenv("SAHINAKSHA_ENABLE_SAM", "0") == "1" and bool(os.getenv("SAHINAKSHA_SAM_CHECKPOINT")),
            "custom_yolo_configured": YOLO_MODEL_PATH.exists(),
        },
        "trained_model": {
            "available": MODEL_PATH.exists() and MODEL_PATH.stat().st_size >= 128,
            "path": MODEL_PATH.name,
        },
    }
