# SahiNaksha API Contract

## 1. Authentication
All FastAPI application endpoints that access analysis data require Authorization: Bearer <supabase_access_token>.
The frontend obtains the access token from the active Supabase Auth session and sends it to FastAPI.
FastAPI validates the token against Supabase Auth, then forwards the same user token to Supabase PostgREST so database RLS evaluates the request as that authenticated user.

## 2. POST /analyze
Authenticated multipart request.
Required fields: file, project_id, survey_id.
Optional fields: reference_parcels, ground_truth, dsm.
The backend verifies that the selected survey belongs to an accessible project.
The endpoint creates a processing_jobs row, executes the existing AI/GIS pipeline, then persists parcels, PostGIS native geometry, validation issues, the completed result snapshot, and survey status.

## 3. Analysis response
Returned data includes analysis_id, project_id, survey_id, processing_job_id, status, original image URL, and the existing analysis result structures.

## 4. GET /analysis/{analysis_id}
Authenticated. Returns an analysis only when its linked survey is accessible to the authenticated user.

## 5. GET /analysis/{analysis_id}/metrics
Authenticated. Returns parcel, topology, validation, review-priority, and evaluation metrics.

## 6. Validation endpoints
GET /analysis/{analysis_id}/validation supports severity, issue_type, status, and parcel_id filters.
GET /analysis/{analysis_id}/validation/summary returns validation and review-priority summaries.
GET /analysis/{analysis_id}/validation/parcels/{parcel_id} returns parcel-specific validation and explainable review information.

## 7. GET /analysis/{analysis_id}/export
Authenticated. Returns GeoJSON and records an exports audit row.

## 8. GET /surveys/{survey_id}/latest-result
Authenticated. Returns the latest completed processing job and its persisted result_snapshot. The frontend uses this to reopen a completed survey after refresh or a new login.

## 9. Direct Supabase operations
Project/survey CRUD and authoritative review persistence use the Supabase JavaScript client with the authenticated session.
Review persistence updates the parcels row, stores edited geometry/properties, inserts a reviews history row, and updates PostGIS native geometry through the set_parcel_native_geometry RPC.

## 10. Security
Typical responses: 400 invalid input, 401 missing/invalid/expired token, 403 unauthorized project/survey, 404 missing resource, 500 processing/persistence failure.
Never put a Supabase secret/service key in React source, VITE_* variables, Git, browser localStorage, or request bodies. Only the publishable key belongs in the frontend environment.

## 11. Geometry CRS rule
The current AI output is image-local normalized 0..100 geometry. It is stored in PostGIS with SRID 0 and explicitly labelled LOCAL_IMAGE_0_100. The application does not invent EPSG:4326.