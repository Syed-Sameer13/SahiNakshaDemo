# SahiNaksha Demo Script

## Goal
Demonstrate the complete workflow from synthetic survey input to final reviewed exports.

## 1. Prepare
1. Start FastAPI and the React frontend.
2. Apply `supabase/migrations/20261004_standardize_api_processing.sql` to the existing Supabase project.
3. Sign in.
4. Open `demo_data/README.md` and confirm that the dataset is synthetic.

## 2. Create workspace
1. Create project: **Synthetic Village Demo**.
2. Create survey: **Synthetic Survey 01**.

## 3. Upload
Upload a PNG conversion of `demo_data/sample_orthomosaic.ppm`.
Optionally upload `demo_data/reference_parcels.geojson` as reference GIS.

The system records an `upload` audit event.

## 4. Process
Start processing.

Show:
- QUEUED
- PROCESSING
- COMPLETED or FAILED

Do not present percentage values as model progress. The database job state is authoritative.

The system records processing start/completion audit events.

## 5. Review
Open the parcel map.

For at least one parcel:
- edit a boundary;
- save the parcel;
- accept one parcel;
- reject one parcel;
- request field verification for one parcel.

Show validation issues and review priority.

The system records:
- parcel_edited
- parcel_verified
- parcel_rejected
- field_verification_requested

## 6. Final export
Use:
- **Final GeoJSON**
- **Final CSV**
- **PDF Survey Report**

Exports are generated from the current Supabase/PostGIS parcel state, not the original AI result snapshot.

The GeoJSON should contain final reviewed geometry, attributes, validation summary and provenance.

The CSV should contain:
`parcel_id, area_sq_m, perimeter_m, review_priority, review_status, validation_issue_count, reference_area, area_difference_percent, reviewer`

The PDF should show:
- SahiNaksha / Preliminary Cadastral Survey Report
- project and survey information
- processing date
- input imagery
- CRS
- model
- parcel summary
- validation summary
- parcel table
- limitations statement

Each export creates an `export_generated` audit event.

## 7. Closing statement
Always state:

> AI-generated boundaries are preliminary and require surveyor verification. They must not be interpreted as legally authoritative cadastral boundaries.

## Demo evidence
For judging, show the database-backed review state, the audit trail, and the three final export files.