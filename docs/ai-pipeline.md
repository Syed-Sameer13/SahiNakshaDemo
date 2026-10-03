# SahiNaksha AI Pipeline

## Purpose

SahiNaksha uses AI to produce **preliminary physical-feature and boundary evidence** from aerial/orthomosaic imagery. The pipeline does **not** automatically determine legal cadastral, ownership, or title boundaries.

Final cadastral geometry remains editable, reviewable, and approvable by a human surveyor and/or authoritative GIS workflow.

## Primary pipeline

RGB orthomosaic / supported raster
        |
        v
Raster validation + conservative preprocessing
        |
        v
HOTOSM DINOv3 building segmentation (when configured and loadable)
        |
        v
SAM automatic-mask refinement/fusion
        |
        v
Segmentation masks
        |
        v
Vector polygons
        |
        v
Geometry cleanup + deduplication
        |
        v
GIS validation / review-priority scoring
        |
        v
Human surveyor review

The implementation keeps the existing model components and routes them through model_router.py.

## Provider order

1. HOTOSM DINOv3 building model — primary building-mask provider when the configured ONNX model is available.
2. SAM refinement/fusion — the existing SAM implementation in ai_segmentation.py, invoked by sam_refinement.py when HOTOSM succeeds.
3. SAM direct — used when HOTOSM is unavailable but SAM is configured.
4. Custom YOLO segmentation — optional project-specific learned provider.
5. Trained pixel model — optional RandomForest RGB/HSV/LAB pixel classifier.
6. OpenCV deterministic fallback — always available when the base OpenCV stack can read the image.

The last two learned providers are secondary alternatives; they are not presented as legal cadastral engines.

## Status model

The pipeline uses these statuses:

- MODEL_AVAILABLE — a provider was found/configured and loaded.
- MODEL_UNAVAILABLE — a provider is missing, disabled, cannot be imported, or fails to load/infer.
- FALLBACK_ACTIVE — deterministic OpenCV processing is being used because learned providers were unavailable.
- PROCESSING — an individual AI stage is running; this is emitted in backend logs because /analyze is currently synchronous.
- COMPLETED — analysis returned a usable result.
- FAILED — reserved for a complete pipeline failure when neither learned nor deterministic processing can return a result.

A normal response includes ai_status, ai_engine.status, model_metadata, provider attempts, and fallback information.

## Inputs

### Supported now

- JPG/JPEG RGB aerial or orthomosaic images.
- PNG RGB aerial or orthomosaic images.
- Maximum upload size is currently 20 MB.
- Existing parcel reference: JSON/GeoJSON.
- Optional aligned DSM prototype input: JPG/JPEG/PNG.

The current image pipeline preserves image-local normalized coordinates (0..100). It does not yet perform arbitrary GeoTIFF CRS transformation.

### Expected imagery

For a useful SIH demonstration, prefer:

- high-resolution RGB orthomosaic/drone imagery;
- visible building roofs/footprints;
- limited severe blur or compression;
- consistent illumination;
- enough spatial resolution that buildings are represented by meaningful regions.

## Outputs

Each learned provider produces FeatureCollections for:

- building footprints;
- road/road-area evidence where available;
- preliminary parcel blocks only where the current provider explicitly generates them.

The vector stage converts segmentation masks/contours into polygons in the existing image-local coordinate convention.

Every polygon then passes through common cleanup:

- discard empty/tiny geometry;
- repair invalid geometry using topology-preserving geometry repair;
- simplify within a small configurable tolerance;
- remove duplicate or near-identical polygons;
- mark geometry validity;
- retain model-source/evidence metadata.

The current deterministic OpenCV fallback produces feature evidence but does not claim segmentation-model confidence.

## Explainable evidence

Feature properties may include:

- model_provider;
- source_model;
- model_source;
- confidence only when the underlying model exposes a genuine confidence/quality value;
- confidence_available;
- boundary_evidence when an image/geometry evidence score exists;
- geometry_valid;
- geometry metrics such as rectangularity, solidity, edge support;
- review_required.

### Confidence rule

SahiNaksha does not fabricate probabilities.

Examples:

- Custom YOLO: detector confidence is available from the model output.
- Trained pixel model: confidence is reported only when the loaded estimator exposes usable predict_proba output.
- SAM: its predicted_iou is retained as model mask-quality evidence when available; the pipeline does not turn a geometry heuristic into a fake probability.
- HOTOSM: per-mask model probability evidence is retained only when available from the ONNX output.
- OpenCV: no model confidence is reported.

## Model configuration

Optional model locations are controlled by environment variables:

SAHINAKSHA_HOTOSM_MODEL
SAHINAKSHA_HOTOSM_MODEL_VERSION
SAHINAKSHA_HOTOSM_STRIDE
SAHINAKSHA_HOTOSM_THRESHOLD

SAHINAKSHA_SAM_CHECKPOINT
SAHINAKSHA_SAM_MODEL_TYPE
SAHINAKSHA_ENABLE_SAM
SAHINAKSHA_SAM_MODEL_VERSION

SAHINAKSHA_YOLO_MODEL
SAHINAKSHA_YOLO_CONF
SAHINAKSHA_YOLO_IMGSZ
SAHINAKSHA_YOLO_DEVICE
SAHINAKSHA_YOLO_MODEL_VERSION

SAHINAKSHA_PIXEL_MODEL_PATH
SAHINAKSHA_PIXEL_MODEL_VERSION

SAHINAKSHA_DISABLE_AI
SAHINAKSHA_MIN_FEATURE_AREA
SAHINAKSHA_SIMPLIFY_TOLERANCE

If an optional checkpoint or package is missing, the application records MODEL_UNAVAILABLE and continues to the next provider.

Model version defaults to unknown unless explicitly configured. The pipeline never invents a version.

## Model provenance

### HOTOSM / DINOv3

The configured file is backend/models/hotosm_dinov3s_buildings.onnx. The application records the configured model path and optional environment-provided version. The exact checkpoint provenance should be recorded in deployment configuration before an SIH presentation.

### SAM

The existing implementation uses Meta's Segment Anything Python package and a configured checkpoint. The application records the configured checkpoint/model type and optional version. SAM is used for physical feature segmentation/refinement, not legal parcel determination.

### SahiNaksha trained pixel model

The optional sahinaksha_pixel_model.joblib is a project-specific RGB/HSV/LAB/edge/vegetation classifier. Its class contract is background/building/road.

### Custom YOLO

The optional sahinaksha_seg.pt model is a project-specific Ultralytics segmentation model with the existing building/road class convention.

### OpenCV fallback

The fallback is deterministic image-processing evidence based on edges, vegetation masking, conservative geometric filters, and Hough-line road evidence. It is not an AI model.

## Failure handling

Expected failures include:

- missing model file;
- invalid/corrupt model checkpoint;
- optional Python dependency not installed;
- incompatible ONNX input/output shape;
- unsupported SAM checkpoint/model type;
- image decode failure;
- insufficient segmentation candidates;
- excessive image size/complexity;
- memory or CPU resource exhaustion.

The router catches provider-specific failures, logs them, and continues to the next provider. A missing learned model must not crash the complete application.

The deterministic OpenCV path is the final safety net.

## Smoke testing

backend/tests/test_ai_smoke.py creates three small RGB aerial-like scenes and verifies:

1. the image can pass through the complete analysis contract;
2. deterministic fallback is usable when AI is explicitly disabled;
3. the response contains building and parcel FeatureCollections;
4. fallback status is exposed.

For real model validation, run the same smoke workflow against at least three representative orthomosaic/drone images with the desired model environment enabled. A green smoke test does not establish cadastral accuracy.

## SIH demonstration acceptance flow

Upload image
  -> validate/read raster
  -> run configured AI provider
  -> generate segmentation evidence
  -> vectorize
  -> clean/repair/deduplicate polygons
  -> validate
  -> return GeoJSON + AI metadata
  -> display AI/fallback status
  -> human surveyor reviews/edits/approves

If the primary learned provider fails, the user receives a result marked with fallback information rather than an unexplained application error.

## Limitations

- RGB imagery alone cannot reveal legal ownership or title boundaries.
- AI-detected building footprints are physical-feature evidence, not parcel ownership evidence.
- Preliminary parcel blocks generated from image/road evidence are explicitly non-legal.
- Current coordinates are image-local normalized coordinates until the geospatial transformation phase is implemented.
- The current DSM path provides relative height evidence from an aligned image raster, not a full geospatial DTM/DSM workflow.
- Model confidence is not the same thing as cadastral accuracy.
- Human surveyor review remains mandatory before treating geometry as final.
