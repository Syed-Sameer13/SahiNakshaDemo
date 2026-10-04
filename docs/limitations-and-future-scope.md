# SahiNaksha Limitations and Future Scope

## Current limitations

1. SahiNaksha produces preliminary physical-feature and cadastral-candidate evidence. It does not determine legal ownership, title, or authoritative cadastral boundaries.
2. AI-generated boundaries are preliminary and require surveyor verification. They must not be interpreted as legally authoritative cadastral boundaries.
3. Final exports are generated from the current Supabase/PostGIS reviewed state, but legal authority still depends on authoritative survey/cadastral data and human approval.
4. Without reliable georeferencing/CRS, real-world area and perimeter cannot be claimed.
5. Reference GIS can be outdated, incomplete, inaccurate, or differently aligned.
6. Reference mismatch identifies a condition for investigation; it does not prove that AI geometry is wrong.
7. RGB imagery is affected by shadows, occlusion, vegetation, roofs, seams, resolution and capture conditions.
8. Current upload accepts JPG/JPEG/PNG imagery. GeoTIFF requires explicit ingestion and georeferencing integration.
9. Current reference ingestion supports GeoJSON/JSON; Shapefile and GeoPackage are not silently treated as implemented.
10. FastAPI BackgroundTasks is suitable for the prototype but is not a durable distributed job system. Production should use a durable worker/queue architecture.
11. Audit events are database-backed and project-scoped. Production should add immutable/append-only controls, retention policy, actor roles and centralized monitoring.
12. PDF reporting is a survey review report for the prototype. It is not a government-certified cadastral document.
13. Synthetic demo data is not evidence of model accuracy.

## Output and reporting

- GeoJSON reads final parcel geometry from PostGIS through a security-invoker export RPC.
- CSV and PDF are built from the same database parcel, validation, survey and processing state at export time.
- GeoJSON includes parcel attributes, review status, validation summary and provenance metadata.
- CSV contains parcel ID, area, perimeter, review priority/status, validation issue count, reference area, area difference and reviewer.
- PDF contains project/survey information, processing details, summary, validation summary, parcel table and the required legal-status limitation.
- Reviewer identity is currently represented by the authenticated reviewer UUID. A production system can add a surveyor profile/display-name table.
- Audit events cover upload, processing started/completed/failed, parcel edit, parcel verification/rejection, field-verification requests and export generation.

## Future scope

### Geospatial production support
GeoTIFF/COG ingestion, CRS validation, datum/unit handling, ground-control points, Shapefile/GeoPackage support and authoritative coordinate transformations.

### Model quality
Calibrated boundary models, stronger DINOv3/HOTOSM/SAM fusion, regional training datasets, uncertainty calibration and held-out accuracy evaluation.

### Review and governance
Surveyor roles, assignments, immutable audit logs, evidence attachments, approval workflows, digital signatures and role-based export permissions.

### Scalable processing
Durable worker queues, object storage, resumable uploads, retry policies, distributed processing and monitoring.

### Reporting
Official templates, configurable project rules, multilingual reports, signed PDFs, map layouts, QR verification and export versioning.

### Validation
Configurable thresholds, stronger topology/coverage analysis, spatial indexing and automated comparison against authoritative reference datasets.
