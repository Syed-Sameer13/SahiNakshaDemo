# SahiNaksha WebGIS Workflow

React + Leaflet workflow: Login → Project Dashboard → Create Project → Create Survey → Upload Orthomosaic → Optional GIS/DSM/Ground Truth → Backend validation → FastAPI processing → Result Map → Parcel Selection → Explainable Validation → Geometry Editing → Review Save → Final Map → Export.

## Backend connection

The frontend reads the FastAPI base URL only from VITE_API_URL. No production code depends on localhost. The analysis request is sent as multipart form data to POST /analyze.

The backend returns AI results, raster metadata, candidate parcels, reference comparison, validation issues, review priority and topology statistics.

## Supabase workflow

Supabase Auth controls login. Project and survey metadata are stored in projects and surveys. Review actions are persisted to parcels with status, reviewer, review score/priority, editable properties and last-updated information.

## Processing states

Uploading; Validating; Processing; Generating polygons; Running topology validation; Saving results; Complete.

## Map layers

Orthomosaic, candidate parcels, reference parcels, buildings/features, roads, selected parcel, edited geometry and final reviewed geometry.

## Review workflow

The surveyor can Accept, Needs Review, Reject, or Request Field Verification. Existing vertex dragging, add/delete vertex, undo, redo, reset and draw-new-polygon tools are preserved.

## Production configuration

Required frontend variables: VITE_API_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY.

## Prototype boundary

The backend currently performs synchronous /analyze processing. The frontend presents explicit processing stages around the real request. Production scale should add asynchronous job IDs, persistent analysis records, object storage, server-side review persistence and authenticated FastAPI authorization.
