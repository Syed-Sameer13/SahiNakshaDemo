# SahiNaksha Final Status

## Release-gate status

**STATUS: NOT COMPLETE / NOT YET DEMO-CERTIFIED**

This is the stabilization review of the main branch. The repository was source-reviewed against the requested end-to-end test plan. Runtime execution against the real Supabase project, Render deployment, browser session, and deployed AI artifacts was not available in this verification session. Those checks are therefore not marked passed.

The release gate remains blocked by unexecuted runtime/integration verification. Source inspection alone is not being treated as proof of completion.

## Stabilization changes made
- Frontend upload now uses the documented upload → process → processing-status → results workflow.
- Frontend final GeoJSON, CSV and PDF actions now call the authoritative backend export endpoints.
- Final exports are generated from the persisted Supabase/PostGIS reviewed state.
- No new AI/GIS feature was added in this phase.

## Test results
Legend: SOURCE-VERIFIED means inspected in the repository. RUNTIME-UNVERIFIED means it still requires execution. BLOCKED means the required live environment was unavailable.

### TEST 1 — AUTH
- Login: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Logout: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Session persistence: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Protected routes: SOURCE-VERIFIED / RUNTIME-UNVERIFIED

### TEST 2 — PROJECT
- Create project: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Open project: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Create survey: SOURCE-VERIFIED / RUNTIME-UNVERIFIED

### TEST 3 — UPLOAD
- Valid JPG/JPEG/PNG orthomosaic: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Invalid file: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Missing file: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Unsupported format: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Missing/ambiguous CRS is not silently invented: SOURCE-VERIFIED / RUNTIME-UNVERIFIED

### TEST 4 — AI
- Primary model: RUNTIME-UNVERIFIED
- Segmentation: RUNTIME-UNVERIFIED
- Polygon extraction: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Fallback: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Model metadata/provenance: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Fake confidence: SOURCE-VERIFIED; fabricated fixed confidence is not intended.

### TEST 5 — GIS
- CRS handling: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Pixel/map conversion: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Area: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Perimeter: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Geometry validity: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Reference comparison: SOURCE-VERIFIED / RUNTIME-UNVERIFIED

### TEST 6 — VALIDATION
- Overlap: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Gap: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Invalid geometry: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Area mismatch: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Reference mismatch: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Building outside parcel: SOURCE-VERIFIED / RUNTIME-UNVERIFIED

Automated backend test files are present for cadastral engine, validation, review score and area metrics, but the suite was not executed in this verification session.

### TEST 7 — REVIEW
- Parcel selection: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Geometry editing: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Undo/redo: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Save: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Accept/reject/field verification: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Refresh persistence: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Edited geometry uses the PostGIS geometry RPC: SOURCE-VERIFIED

### TEST 8 — EXPORT
- GeoJSON: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- CSV: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- PDF: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Export source is final Supabase/PostGIS state: SOURCE-VERIFIED
- Export audit trail: SOURCE-VERIFIED / RUNTIME-UNVERIFIED

### TEST 9 — DEPLOYMENT
- Production API URL through VITE_API_URL: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- No localhost dependency in production frontend configuration: SOURCE-VERIFIED
- Frontend build: RUNTIME-UNVERIFIED
- Backend environment variables: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Source secret safety: source configuration uses placeholders and .env is ignored; this is not a complete secrets audit.
- Health endpoint: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Supabase RLS: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- PostGIS geometry: SOURCE-VERIFIED / RUNTIME-UNVERIFIED
- Render backend/frontend/AI runtime: BLOCKED / RUNTIME-UNVERIFIED because the Render workspace was not available.

## Production file-persistence limitation
The current prototype writes uploaded imagery and analysis snapshots to the backend filesystem. This is acceptable only for a controlled same-instance demonstration. It is not a production persistence guarantee for an ephemeral Render filesystem.

For production, inputs should be stored in Supabase Storage or another durable object store, with database records holding object keys/URLs. Until that is implemented and tested, deployment must be described as a prototype deployment with ephemeral file-storage constraints.

## TEST 10 — SIH DEMO
The requested Login → Project → Survey → Upload → Validate → AI → Processing → Map → Parcel Review → Edit → Save → Accept/Field Verification → Final Map → GeoJSON/PDF sequence is implemented in source, but the complete sequence was not executed end-to-end against the live deployment in this verification session.

## COMPLETED
- Standardized FastAPI survey workflow.
- Structured API errors.
- Protected backend operations with bearer authentication.
- Supabase/PostGIS persistence model and RLS migration.
- Processing job states and metadata.
- AI routing with explicit fallback architecture.
- CRS-aware GIS calculations.
- Topology and validation checks.
- Deterministic review-risk scoring.
- Human review and geometry editing persistence.
- Audit event model.
- Final-state GeoJSON/CSV/PDF backend exports.
- Demo dataset and documentation.
- Standardized frontend upload/process/results workflow.
- Backend-connected final export controls.

## PARTIALLY COMPLETED
- Full browser workflow: implementation exists; live browser execution is unverified.
- Primary AI execution: implementation exists; deployed model availability is unverified.
- Real georeferenced orthomosaic: implementation exists; runtime test is unverified.
- Render deployment: configuration exists; live service test is unverified.
- Refresh/reopen persistence: implementation exists; live test is unverified.
- Export byte-level comparison with final DB state: implementation is source-verified; runtime comparison is unverified.

## KNOWN LIMITATIONS
1. Current imagery upload supports JPG/JPEG/PNG; GeoTIFF/COG is not implemented.
2. Without reliable CRS/georeferencing, real-world area/perimeter cannot be claimed.
3. Reference GIS can be incomplete or differently aligned.
4. AI boundaries are preliminary and require surveyor verification.
5. FastAPI BackgroundTasks is prototype-grade rather than a durable distributed queue.
6. Render local filesystem storage is not durable production object storage.
7. Reviewer display name is separate from the authoritative authenticated reviewer UUID.
8. PDF is a prototype survey review report, not a certified cadastral document.
9. Synthetic demo data does not establish model accuracy.

## FUTURE SCOPE
- Supabase/object storage for uploaded inputs and generated artifacts.
- Durable worker/queue processing.
- GeoTIFF/COG and authoritative CRS workflows.
- Calibrated AI models and held-out accuracy evaluation.
- Surveyor roles and permissions.
- Immutable audit retention.
- Official report/map templates and signed exports.
- Production monitoring, retries and resumable uploads.

## DEMO READY FEATURES
When required services and model artifacts are available, the implemented path is: Login → Create Project → Create Survey → Upload Orthomosaic → Validate → Start AI Analysis → Processing Status → Orthomosaic Map → AI Features → Candidate Parcels → Reference Parcels → Select Parcel → Area/Review Priority/Validation/Reference Comparison → Edit Boundary → Undo/Redo → Save → Accept or Request Field Verification → Final Reviewed Map → GeoJSON/CSV/PDF.

## KNOWN RISKS
- End-to-end runtime test is not completed.
- Live Render deployment is not verified.
- Live Supabase authentication/RLS/PostGIS workflow is not verified.
- Primary AI model availability on deployment is not verified.
- Render filesystem durability is not suitable for a production persistence guarantee.
- Large orthomosaics may exceed prototype upload/time limits.
- Background processing can be interrupted on an ephemeral/free deployment.

## Final release decision
**DO NOT MARK SahiNaksha COMPLETE YET.**

The source implementation is substantially prepared for the SIH workflow, but the explicit release criterion requires a complete end-to-end runtime test. That criterion has not been satisfied by source inspection alone.