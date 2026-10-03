# SahiNaksha Data Model

## 1. Current persistence model

SahiNaksha currently has two separate data layers:

1. Prototype analysis storage in backend JSON/filesystem.
2. Supabase/PostGIS schema prepared for future persistent project/survey data.

They must not be documented as if they are already one integrated database.

## 2. Runtime analysis object

The current `/analyze` pipeline produces a dictionary containing fields such as:

```
analysis_id
status
original_image_url
buildings
roads
parcels
analysis_mode
ai_engine
cadastral_mode
validation
topology_stats
evaluation
```

### Feature collections

`buildings`, `roads`, and `parcels` use GeoJSON FeatureCollection structures.

Feature properties can contain evidence and review fields such as:
- feature/parcel identifier,
- confidence,
- model provider,
- review_required,
- boundary_evidence,
- geometry_valid,
- review_score,
- review_priority,
- land_use,
- topology_repaired,
- area_sq_m where valid.

The exact properties vary by provider and processing path.

## 3. Backend prototype storage

`backend/app/services/storage.py` provides:

```
AnalysisStore
  save(analysis_id, payload)
  load(analysis_id)
```

Files are written under:

```
backend/outputs/analyses/<analysis_id>.json
```

The API also maintains an in-process `ANALYSES` dictionary.

This is prototype persistence, not the final database architecture.

## 4. Supabase/PostGIS schema

Source:
`supabase/schema.sql`

### projects

| Column | Type | Purpose |
|---|---|---|
| id | uuid | Project identifier |
| owner_id | uuid | References `auth.users` |
| name | text | Project name |
| description | text | Optional description |
| created_at | timestamptz | Creation time |

RLS currently permits the project owner to manage the project.

### surveys

| Column | Type | Purpose |
|---|---|---|
| id | uuid | Survey identifier |
| project_id | uuid | Parent project |
| name | text | Survey name |
| source_image_url | text | Source image location |
| source_crs | text | Source CRS |
| status | text | Survey status |
| created_at | timestamptz | Creation time |

### parcels

| Column | Type | Purpose |
|---|---|---|
| id | uuid | Database identifier |
| survey_id | uuid | Parent survey |
| parcel_id | text | Domain parcel identifier |
| geom | geometry | PostGIS geometry, SRID 4326 |
| area_sq_m | double precision | Area |
| review_score | double precision | Review-priority score |
| review_priority | text | Priority category |
| status | text | Candidate/review state |
| properties | jsonb | Additional attributes |
| created_at | timestamptz | Creation time |

### validation_issues

| Column | Type | Purpose |
|---|---|---|
| id | uuid | Issue identifier |
| survey_id | uuid | Parent survey |
| parcel_id | text | Optional affected parcel |
| issue_type | text | Issue category |
| severity | text | Severity |
| description | text | Explanation |
| resolved | boolean | Resolution state |
| created_at | timestamptz | Creation time |

## 5. Authentication and authorization model

Current:
- Supabase Auth exists in the frontend.
- Database RLS uses `auth.uid()`.
- FastAPI does not currently enforce the Supabase user identity.

Therefore database authorization is prepared, but API-level identity propagation is incomplete.

## 6. Surveyor workflow data

Target persistent entities:

```
User
  └─ Project
       └─ Survey
            ├─ source datasets
            ├─ processing status
            ├─ parcel candidates
            ├─ validation issues
            ├─ review decisions
            └─ exports
```

Only part of this hierarchy is currently runtime-backed.

## 7. Administrator data

No administrator-specific tables or role claims are currently implemented.

Administrator role/RBAC should be added only when the admin workflow is implemented. Do not infer admin privileges from the current project-owner RLS policy.

## 8. Data lifecycle

Current:

```
Upload
 → temporary file
 → analysis
 → JSON analysis store
 → API response
 → browser localStorage review state
 → browser GeoJSON export
```

Planned production lifecycle:

```
Upload
 → project/survey record
 → validated source datasets
 → processing status
 → PostGIS candidate features
 → validation/review
 → persistent review decisions
 → export package
 → audit history
```

## 9. Geospatial data constraints

The current implementation is not a general geospatial ETL engine.

Reference parcel refinement currently expects image-local normalized coordinates from 0 to 100. Although the database schema uses PostGIS geometry with SRID 4326, the current analysis service does not perform the transformation needed to safely move arbitrary geographic coordinates into image-local coordinates.

This must be resolved before claiming full georeferenced cadastral processing.
