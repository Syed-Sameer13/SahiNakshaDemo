# SahiNaksha Architecture

## 1. Purpose

SahiNaksha is an AI-assisted preliminary cadastral mapping prototype for survey-support workflows. It combines raster/image evidence, optional reference GIS, AI feature extraction, geometry processing, validation, review prioritization, human editing, and GeoJSON export.

The architecture documented here reflects the implementation currently present in the repository. Capabilities described as planned are explicitly marked as planned and are not presented as working features.

## 2. Architecture

```
Surveyor Browser
  React + Vite + React-Leaflet
  ├─ Authentication gate (Supabase Auth)
  ├─ Upload / analysis history
  ├─ Map visualization and editing
  └─ Local review state
          |
          | HTTP JSON / multipart
          v
FastAPI
  ├─ /health
  ├─ /analyze
  └─ /analysis/{id}*
          |
          v
Analysis Service
  ├─ AI model router
  │   ├─ Custom YOLO (when artifact exists)
  │   ├─ trained pixel model (when valid artifact exists)
  │   ├─ HOTOSM ONNX (when artifact exists)
  │   └─ SAM (when available)
  ├─ OpenCV fallback
  ├─ Cadastral/refinement services
  ├─ Topology repair
  ├─ Geometry validation
  ├─ Area metrics
  ├─ Review-priority scoring
  └─ Ground-truth evaluation
          |
          +---- Prototype filesystem analysis store
          |
          +---- Supabase/PostGIS schema exists, but is NOT the
                runtime persistence layer of /analyze today
          |
          v
GeoJSON response / GeoJSON export

Planned production persistence:
FastAPI services -> Supabase/PostGIS -> project/survey/parcel/review/audit state
```

No Node.js/Express service is required by the current implementation.

## 3. User roles

### Surveyor — partially implemented

Currently implemented:
- Authentication gate.
- Image/GIS upload.
- Analysis execution.
- Map layer viewing.
- Feature inspection.
- Attribute editing.
- Geometry editing.
- Review decisions.
- Local review persistence.
- GeoJSON download.

Not yet implemented as a complete product workflow:
- Persistent project creation in Supabase.
- Persistent survey records.
- Server-side review save.
- Server-side audit trail.
- Field-verification workflow as a first-class persisted state.
- PDF/CSV report export.

### Administrator — not implemented

The Supabase schema currently supports project ownership by `auth.users`, but there is no administrator UI/API/RBAC implementation for:
- user management,
- project administration,
- processing dashboards,
- audit/review monitoring.

These are planned capabilities and must not be described as currently available.

## 4. Current frontend boundary

Primary frontend modules:
- `frontend/src/App.jsx`: application state and local analysis history.
- `frontend/src/components/AuthGate.jsx`: Supabase authentication gate.
- `frontend/src/components/UploadPanel.jsx`: upload and analysis initiation.
- `frontend/src/components/Dashboard.jsx`: map, review, geometry editing, attributes and final GeoJSON download.
- `frontend/src/lib/supabase.js`: Supabase client.
- `frontend/src/styles.css`: presentation.

The frontend currently keeps review edits and analysis history in browser localStorage.

## 5. Current backend boundary

The repository currently keeps most backend modules under `backend/app/services/`. The requested logical boundaries are documented below without forcing a risky directory migration.

### routes
Current physical location:
- `backend/app/routes.py`

Responsibilities:
- HTTP request validation.
- File upload handling.
- Calling the analysis service.
- Returning analysis/metrics/export responses.

### services
Current physical location:
- `backend/app/services/`

Responsibilities:
- `analysis.py`: orchestration of the processing pipeline.
- `model_router.py`: AI provider selection/fallback.
- `yolo_segmentation.py`: custom YOLO inference.
- `trained_segmentation.py`: trained pixel-model inference.
- `hotosm_building_segmentation.py`: HOTOSM ONNX inference.
- `ai_segmentation.py`: SAM-based inference.
- `opencv_analysis.py`: non-ML fallback extraction.
- `cadastral_engine.py`: reference parcel loading/refinement and evidence enrichment.
- `topology_engine.py`: geometry repair and overlap handling.
- `validation.py`: geometry/noise/overlap validation.
- `area_metrics.py`: area enrichment.
- `review_score.py`: deterministic review-priority scoring.
- `metrics.py`: ground-truth evaluation.
- `export_service.py`: GeoJSON response serialization.
- `storage.py`: prototype disk-backed analysis persistence.

### models
There is currently no dedicated `backend/app/models/` package. Database models are represented by Supabase SQL rather than an ORM.

### schemas
There is currently no dedicated `backend/app/schemas/` package. FastAPI currently relies on UploadFile and plain dictionaries for analysis payloads.

### utils
There is currently no dedicated `backend/app/utils/` package.

These missing packages are documentation-level architectural boundaries, not a reason to create empty directories immediately. They should be introduced only when typed API schemas, database models, or shared utilities are actually needed.

## 6. Processing pipeline actually implemented

Current sequence:

1. Upload validation and file-size/type checks.
2. AI model router.
3. Fallback to OpenCV when no AI provider is available.
4. Optional reference parcel loading/refinement.
5. Empty parcel collection guard.
6. Topology repair and overlap handling.
7. Land-use evidence classification.
8. Optional relative-height evidence from aligned DSM.
9. Geometry validation.
10. Area enrichment.
11. Explainable deterministic review-priority scoring.
12. Optional ground-truth IoU evaluation.
13. Analysis metadata assembly.
14. Filesystem persistence.
15. JSON/GeoJSON response.

Important implementation limits:
- Current upload API accepts JPG/PNG imagery, not general GeoTIFF.
- Reference parcel refinement currently expects image-local normalized coordinates 0..100.
- It does not currently transform arbitrary geographic CRS coordinates into image coordinates.
- DSM is currently an aligned JPG/PNG grayscale raster, not a general geospatial DSM/DTM reader.
- AI segmentation produces feature evidence; RGB imagery alone is not treated as authoritative ownership information.
- Final browser GeoJSON is explicitly preliminary and requires authoritative survey/cadastral validation.

## 7. Data persistence

Current runtime:
- Uploaded files: `backend/uploads/`
- Analysis JSON: `backend/outputs/analyses/`
- In-process cache: `ANALYSES` dictionary.

Database foundation:
- `supabase/schema.sql`
- PostGIS extension.
- projects, surveys, parcels, validation_issues tables.
- RLS policies for project owners.

The current API does not yet write analysis results into those tables.

## 8. Export boundary

Implemented:
- GeoJSON through `GET /analysis/{analysis_id}/export`.
- Browser-side final reviewed GeoJSON from the Dashboard.

Not implemented:
- Backend PDF report generation.
- Backend CSV export.
- Authoritative cadastral package generation.

## 9. Deployment boundary

The repository contains deployment configuration for frontend/backend services, but architecture correctness must not depend on a specific hosting provider. The backend is a standalone FastAPI service and the frontend is a standalone Vite build.

## 10. Design principles

1. Preserve React + Leaflet.
2. Preserve FastAPI.
3. Keep AI providers behind `model_router.py`.
4. Keep GIS/validation deterministic and inspectable.
5. Do not treat model confidence as legal cadastral truth.
6. Do not introduce Node/Express unless a concrete requirement appears.
7. Move persistence toward Supabase/PostGIS incrementally rather than rewriting the processing engine.
8. Add typed `schemas/`, `models/`, and `utils/` only when real code needs them.
