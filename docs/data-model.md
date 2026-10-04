# SahiNaksha Data Model

## 1. Authoritative persistence
Supabase Postgres + PostGIS is the authoritative persistence layer for projects, surveys, processing jobs, parcels, validation issues, reviews, and exports.
Browser localStorage is only a temporary UI cache. It is not the source of truth.
Supabase Auth provides the user identity through auth.users.

## 2. Relationship model
User → Project → Survey → Processing Job → Parcels → Validation Issues → Review
Surveys also own export records.

## 3. Existing schema preserved
The original projects, surveys, parcels, and validation_issues tables remain. The schema was extended additively.

## 4. Parcels
Persisted parcel data includes parcel_id, survey_id, PostGIS geometry, geometry coordinate-space/CRS metadata, area, perimeter, AI evidence, deterministic review priority, review status, reviewer, timestamps, reference comparison, and provenance.

Existing geom is retained as the WGS84 geometry column. New geom_native stores the native geometry. The current AI output uses image-local normalized 0..100 coordinates, so those geometries are stored with SRID 0 and geometry_crs=LOCAL_IMAGE_0_100. The application never falsely labels image-local coordinates as EPSG:4326.

## 5. Validation issues
Each issue stores survey_id, parcel_id, issue_type, severity, description, structured evidence, status, resolved flag, and timestamps.

## 6. Processing jobs
processing_jobs stores survey_id, created_by, analysis_id, status, progress, stage, error message, result snapshot, start/completion timestamps, and audit timestamps.
The completed result_snapshot allows a user to reopen the latest result after browser refresh or a new login.

## 7. Reviews
reviews stores survey_id, parcel record, parcel_id, authenticated reviewer, decision, comments, previous status, new status, edited geometry, and timestamp.
The parcel row contains the current review state while reviews preserves decision history.

## 8. Exports
exports stores survey, processing job, authenticated creator, format, status, file metadata, and timestamp.

## 9. Security
RLS is enabled for every application table. A user can manage only projects where owner_id equals auth.uid(). Survey, parcel, validation, processing-job, review, and export access is inherited through survey → project ownership.
Anonymous Data API access is revoked for these application tables. The frontend uses only the Supabase publishable key. No service/secret key is shipped to the browser.
FastAPI also validates the Supabase bearer token and forwards that user token to Supabase PostgREST so RLS remains the database authorization boundary.

## 10. Persistence lifecycle
Login → Project in Supabase → Survey in Supabase → authenticated /analyze request → processing job → AI/GIS processing → parcels/PostGIS → validation issues → completed result snapshot → surveyor review → parcel latest state + review history → export audit record.

Refreshing the browser or logging out does not remove authoritative records.