# SahiNaksha API Contract

## 1. Base URL and authentication

The standardized API is served under `/api`. All project, survey, processing, parcel, validation, review, and export endpoints require:

`Authorization: Bearer <supabase_access_token>`

FastAPI validates the Supabase access token and forwards the same user token to Supabase PostgREST so database RLS remains the authorization boundary.

Health is public:

- `GET /api/health`

## 2. Structured errors

Errors use this shape for HTTP errors and request validation:

```json
{
  "error": {
    "code": "RESULT_NOT_READY",
    "message": "No completed processing result exists for this survey.",
    "details": {}
  }
}
```

Common codes include `VALIDATION_ERROR`, `UNAUTHORIZED`, `PROJECT_NOT_FOUND`, `SURVEY_NOT_FOUND`, `NO_UPLOAD`, `PROCESSING_ACTIVE`, `RESULT_NOT_READY`, `PARCEL_NOT_FOUND`, and `INTERNAL_SERVER_ERROR`.

## 3. Project workflow

### GET /api/projects
Returns projects accessible to the authenticated user.

### POST /api/projects
JSON body:

```json
{"name":"Village Survey","description":"Prototype survey"}
```

Creates an owned project.

### GET /api/projects/{project_id}
Returns one accessible project.

### PATCH /api/projects/{project_id}
JSON body may contain `name` and/or `description`.

## 4. Survey workflow

### GET /api/projects/{project_id}/surveys
Lists surveys belonging to the project.

### POST /api/projects/{project_id}/surveys
JSON body:

```json
{"name":"Orthomosaic Survey 01"}
```

### GET /api/surveys/{survey_id}
Returns survey metadata and recent processing jobs.

## 5. Upload

### POST /api/surveys/{survey_id}/upload

Authenticated multipart upload.

Required:

- `file`: JPG/JPEG/PNG orthomosaic image.

Optional:

- `reference_parcels`: GeoJSON/JSON
- `ground_truth`: GeoJSON/JSON
- `dsm`: JPG/JPEG/PNG prototype input

The upload endpoint stores files under the survey workspace and updates the survey source image. It does not claim that an uploaded image is georeferenced.

## 6. Processing

### POST /api/surveys/{survey_id}/process

Returns HTTP `202 Accepted` and creates a `processing_jobs` row.

The prototype uses FastAPI BackgroundTasks rather than Celery/Redis. The job state is persisted in Supabase, so the frontend polls the database-backed API rather than relying on in-memory progress.

States:

- `QUEUED`
- `PROCESSING`
- `COMPLETED`
- `FAILED`

The API does **not** fabricate percentage progress. A queued/processing job remains at the actual known progress boundary; completion sets progress to 100.

Each job records:

- `started_at`
- `completed_at`
- `status`
- `error_message`
- `model_used`
- `input`
- `output`
- `result_snapshot`

### GET /api/surveys/{survey_id}/processing-status

Returns the latest processing job, including state, timestamps, model, input, output, and error.

## 7. Results

### GET /api/surveys/{survey_id}/results

Returns the latest completed persisted analysis result. If processing is not complete, returns a structured `RESULT_NOT_READY` error.

## 8. Parcels

### GET /api/surveys/{survey_id}/parcels
Returns authoritative persisted parcel records for the survey.

### GET /api/parcels/{parcel_id}
Returns one parcel after verifying access through its survey/project.

### PATCH /api/parcels/{parcel_id}
Supports parcel attributes, properties, review fields, and optional GeoJSON geometry.

When geometry is supplied, the backend writes it through `set_parcel_native_geometry` with SRID 0 unless a future georeferenced workflow explicitly supplies another CRS.

## 9. Human review

### POST /api/parcels/{parcel_id}/verify

Body:

```json
{
  "decision": "ACCEPT",
  "comments": "Boundary reviewed",
  "geometry": null
}
```

Allowed decisions:

- `ACCEPT`
- `NEEDS_REVIEW`
- `REJECT`

### POST /api/parcels/{parcel_id}/request-field-verification

Records `REQUEST_FIELD_VERIFICATION` and changes the parcel to `Needs Field Survey`.

AI output remains preliminary physical-feature evidence. Human surveyor review is required; these endpoints do not make a legal cadastral determination.

## 10. Validation

### GET /api/surveys/{survey_id}/validation

Optional query parameters:

- `severity`
- `issue_type`
- `status`
- `parcel_id`

Returns persisted validation issues.

## 11. Exports

### GET /api/surveys/{survey_id}/export/geojson
Downloads the **final reviewed survey** as GeoJSON. Geometry is read from PostGIS through the security-invoker export RPC at request time; the AI result snapshot is not used as the authoritative geometry source. Each feature includes parcel attributes, review status, validation summary and provenance.

### GET /api/surveys/{survey_id}/export/csv
Downloads the final database-backed parcel state with exactly these columns:

- `parcel_id`
- `area_sq_m`
- `perimeter_m`
- `review_priority`
- `review_status`
- `validation_issue_count`
- `reference_area`
- `area_difference_percent`
- `reviewer`

### GET /api/surveys/{survey_id}/export/report
Downloads a PDF named `sahinaksha-{survey_id}-report.pdf`.

The PDF contains SahiNaksha / Preliminary Cadastral Survey Report, project and survey information, processing date, input imagery, CRS, model, parcel summary, validation summary, parcel table, and the mandatory legal-status limitation.

Every export creates an `exports` row and an `audit_events` row.

## 12. Legacy compatibility endpoints

The existing frontend/integrations remain supported:

- `POST /analyze`
- `GET /analysis/{analysis_id}`
- `GET /analysis/{analysis_id}/metrics`
- `GET /analysis/{analysis_id}/validation`
- `GET /analysis/{analysis_id}/export`
- `GET /surveys/{survey_id}/latest-result`

These are compatibility routes; new frontend integrations should use the standardized `/api` workflow.

## 13. CORS

CORS is configured through:

`CORS_ORIGINS=http://localhost:5173,https://your-frontend.example.com`

When `CORS_ORIGINS` is set, those origins are used. Otherwise local Vite origins are allowed.

## 14. Geometry / CRS rule

Current AI output can be image-local normalized 0..100 geometry. It is stored in `geom_native` with SRID 0 and labelled `LOCAL_IMAGE_0_100`. The API does not invent EPSG:4326 or legal cadastral coordinates.

## 15. Security

Never put a Supabase secret/service key in React source, `VITE_*` variables, Git, browser localStorage, or request bodies. The backend uses the authenticated user's access token for RLS-authorized database operations.


## 14. Audit trail

The `audit_events` table records lifecycle actions including:

- `upload`
- `processing_started`
- `processing_completed`
- `processing_failed`
- `parcel_edited`
- `parcel_verified`
- `parcel_rejected`
- `field_verification_requested`
- `export_generated`

Each event records the authenticated actor, survey, optional parcel/entity, metadata and timestamp. RLS restricts events to the owning project.

## 15. Final export source of truth

Final exports are generated from current Supabase/PostGIS state at request time. The export RPC returns `geom_native` as GeoJSON plus review status, attributes, provenance and reviewer information. Validation issues are queried separately from `validation_issues` and summarized per parcel.

This ensures a geometry edited or a review decision saved after AI processing is reflected in subsequent final exports.

## 16. Geometry / CRS rule

Current AI output can be image-local normalized 0..100 geometry. It is stored in `geom_native` with SRID 0 and labelled `LOCAL_IMAGE_0_100`. The API does not invent EPSG:4326 or legal cadastral coordinates.

## 17. Security

Never put a Supabase secret/service key in React source, `VITE_*` variables, Git, browser localStorage, or request bodies. The backend uses the authenticated user's access token for RLS-authorized database operations.
