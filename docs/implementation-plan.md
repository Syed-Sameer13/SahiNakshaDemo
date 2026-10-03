# SahiNaksha Implementation Plan

This plan is based on the current repository. It prioritizes stabilization and incremental completion instead of a rewrite.

## Phase 0 — Stabilization

Status: mostly completed.

### Objectives
- Remove source corruption.
- Ensure backend imports are valid.
- Ensure frontend source is syntactically valid.
- Preserve current AI/GIS providers.
- Document the actual architecture.

Completed stabilization work includes repair of accidental literal newline corruption in:
- `backend/app/services/trained_segmentation.py`
- `backend/app/services/yolo_segmentation.py`
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/UploadPanel.jsx`

A parcel-pipeline guard was also added to prevent missing parcel collections from reaching topology processing.

## Phase 1 — Make the current MVP reproducible

Priority: immediate.

1. Supply valid model artifacts through deployment storage or model hosting.
2. Verify:
   `python -m compileall app`
3. Verify FastAPI startup.
4. Verify `GET /health`.
5. Run `npm install` and `npm run build`.
6. Run one end-to-end image analysis.
7. Test frontend-to-backend CORS and image serving.
8. Record the verified model/provider actually used.

No architecture change is required.

## Phase 2 — Formalize input validation

Priority: high.

Implement:
- raster metadata inspection,
- explicit CRS presence/validation,
- geospatial raster formats such as GeoTIFF,
- dimensions/resolution checks,
- optional DSM/DTM metadata validation,
- GeoJSON geometry validation,
- consistent validation error schema.

Important: do not call an image "georeferenced" merely because it is an uploaded PNG/JPG.

## Phase 3 — Introduce real geospatial transformation

Priority: high.

Implement a GIS coordinate transformation boundary that:
1. reads source CRS,
2. transforms reference geometry into the orthomosaic/image coordinate system,
3. performs refinement in the correct coordinate space,
4. transforms output back into the declared CRS.

Only after this should the system claim general georeferenced orthomosaic/reference-GIS support.

## Phase 4 — Complete persistence

Priority: high.

Use the existing Supabase/PostGIS schema as the persistence target.

Add incrementally:
- project creation,
- survey creation,
- source dataset metadata,
- processing status,
- parcel persistence,
- validation issue persistence,
- review decisions,
- export metadata.

Keep `AnalysisStore` temporarily as a fallback until the database path is proven stable.

Do not rewrite the AI/GIS processing engine to accomplish this.

## Phase 5 — Backend identity and role authorization

Priority: high.

Implement:
- Supabase access-token verification at FastAPI,
- surveyor ownership checks,
- administrator role/RBAC,
- authorization on project/survey/review endpoints.

Do not expose admin functions merely because a user is authenticated.

## Phase 6 — Surveyor workflow completion

Priority: high.

Implement persistent versions of the existing UI concepts:

```
Login
 → Create Project
 → Create Survey
 → Upload
 → Validate
 → Process
 → Monitor
 → Map
 → Inspect
 → Review evidence
 → Validation issues
 → Reference comparison
 → Edit
 → Approve / Reject / Request Field Verification
 → Save review
 → Export
```

Existing Leaflet editing should be retained.

## Phase 7 — Administrator workflow

Priority: medium.

Add a separate admin area for:
- user/project management,
- project status,
- processing status,
- review/audit information.

This requires actual role authorization and audit records.

## Phase 8 — Explainability and review evidence

Priority: medium.

Expose existing evidence in a structured way:
- model/provider,
- confidence,
- boundary evidence,
- geometry validity,
- validation issues,
- topology changes,
- review score,
- review-priority reasons.

The existing deterministic `review_score.py` should remain explainable and should not be presented as model accuracy.

## Phase 9 — Export expansion

Priority: medium.

Keep current GeoJSON export.

Add only when requirements are confirmed:
- CSV attribute export,
- PDF survey/review report,
- export metadata,
- CRS metadata,
- validation summary,
- review/audit summary.

## Phase 10 — Testing and deployment hardening

Priority: medium.

Add:
- backend unit tests for geometry and scoring,
- API tests,
- model-router fallback tests,
- frontend build checks,
- integration test for upload → analysis → retrieval → export,
- CI pipeline,
- deployment smoke tests.

## Module-boundary plan

The current physical layout under `backend/app/services/` is intentionally retained.

Logical target:

```
backend/app/
├── routes.py                 # current HTTP boundary
├── services/
│   ├── analysis.py           # orchestration
│   ├── model_router.py       # AI provider selection
│   ├── cadastral_engine.py   # cadastral/reference GIS processing
│   ├── topology_engine.py    # geometry repair
│   ├── validation.py         # validation
│   ├── area_metrics.py       # area calculations
│   ├── review_score.py       # review priority
│   ├── metrics.py            # evaluation
│   ├── export_service.py     # exports
│   └── storage.py            # prototype persistence
├── models/                   # add when ORM/domain models are actually needed
├── schemas/                  # add when typed API schemas are actually needed
└── utils/                    # add only for shared utilities
```

Do not move existing services merely to make the directory tree look different.

## Definition of done for the target system

A feature is complete only when:
1. frontend supports it,
2. FastAPI exposes the required contract,
3. persistence is implemented where state must survive sessions,
4. authorization is enforced,
5. validation/error handling is present,
6. tests cover the critical path,
7. documentation describes the implemented behavior.

The final target architecture remains:

```
React + Leaflet
      ↓
FastAPI
      ↓
AI + GIS + Validation Services
      ↓
Supabase/PostGIS
      ↓
GeoJSON / PDF / CSV
```

PDF and CSV are target exports, not current implemented exports.
