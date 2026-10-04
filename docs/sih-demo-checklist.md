# SahiNaksha SIH Demo Checklist

Do not tick a box until it has been visibly completed in the running application.

## 1. Authentication
- [ ] Open deployed SahiNaksha frontend.
- [ ] Login with the demo account.
- [ ] Confirm authenticated project dashboard appears.
- [ ] Refresh and confirm the session remains active.
- [ ] Logout.
- [ ] Confirm protected workflow is no longer accessible.
- [ ] Login again.

## 2. Project and Survey
- [ ] Create Project.
- [ ] Confirm project appears.
- [ ] Open Project.
- [ ] Create Survey.
- [ ] Confirm survey appears.

## 3. Upload and Validation
- [ ] Select a valid JPG/PNG orthomosaic.
- [ ] Confirm preview appears.
- [ ] Attempt processing without an orthomosaic and confirm validation.
- [ ] Test an unsupported file and confirm rejection.
- [ ] Upload reference parcel GeoJSON when available.
- [ ] Confirm missing/ambiguous CRS is not silently invented.
- [ ] Confirm upload status is recorded.

## 4. AI Processing
- [ ] Start AI Analysis.
- [ ] Confirm QUEUED/PROCESSING state.
- [ ] Show processing stage/progress.
- [ ] Confirm primary model/provider metadata when available.
- [ ] Confirm AI features are displayed.
- [ ] Confirm polygons are extracted.
- [ ] Confirm provenance/model metadata.
- [ ] If primary model is unavailable, confirm explicit fallback status.

## 5. GIS
- [ ] Display Orthomosaic.
- [ ] Display AI Features.
- [ ] Display Candidate Parcels.
- [ ] Display Reference Parcels.
- [ ] Confirm CRS.
- [ ] Confirm correct coordinate-space handling.
- [ ] Confirm real area only when valid projected CRS permits it.
- [ ] Confirm perimeter.
- [ ] Confirm geometry validity/topology information.
- [ ] Show Reference Comparison.

## 6. Validation
- [ ] Show overlap.
- [ ] Show gap.
- [ ] Show invalid geometry.
- [ ] Show area mismatch.
- [ ] Show reference mismatch.
- [ ] Show building outside parcel when present.
- [ ] Confirm issue severity/evidence.
- [ ] Confirm review priority is presented as deterministic triage, not probability.

## 7. Human Review
- [ ] Select Parcel.
- [ ] Show Area.
- [ ] Show Review Priority.
- [ ] Show Validation Issues.
- [ ] Show Reference Comparison.
- [ ] Edit Boundary.
- [ ] Drag a vertex.
- [ ] Add a vertex.
- [ ] Delete a vertex.
- [ ] Undo.
- [ ] Redo.
- [ ] Save.
- [ ] Confirm saved-to-Supabase state.
- [ ] Accept a parcel.
- [ ] Reject a test parcel.
- [ ] Request Field Verification for a test parcel.
- [ ] Refresh browser.
- [ ] Reopen survey/results.
- [ ] Confirm edited geometry and review status persist.

## 8. Final Map
- [ ] Switch to Final Reviewed Map.
- [ ] Confirm reviewed/accepted geometry is shown.
- [ ] Confirm rejected/unfinished parcels are not incorrectly presented as accepted final cadastral boundaries.
- [ ] Confirm the preliminary/legal-status limitation is documented.

## 9. Export
- [ ] Generate GeoJSON.
- [ ] Confirm GeoJSON geometry is from reviewed database state.
- [ ] Confirm GeoJSON contains review status, validation summary and provenance.
- [ ] Generate CSV.
- [ ] Confirm parcel_id.
- [ ] Confirm area_sq_m.
- [ ] Confirm perimeter_m.
- [ ] Confirm review_priority.
- [ ] Confirm review_status.
- [ ] Confirm validation_issue_count.
- [ ] Confirm reference_area.
- [ ] Confirm area_difference_percent.
- [ ] Confirm reviewer.
- [ ] Generate PDF Report.
- [ ] Confirm project information.
- [ ] Confirm survey information.
- [ ] Confirm processing date.
- [ ] Confirm input imagery.
- [ ] Confirm CRS.
- [ ] Confirm model used.
- [ ] Confirm candidate/review/accepted/rejected/field-verification summary.
- [ ] Confirm validation errors/warnings/discrepancies.
- [ ] Confirm parcel table.
- [ ] Confirm required limitation statement.
- [ ] Confirm export audit event.

## 10. Deployment
- [ ] Confirm production VITE_API_URL.
- [ ] Confirm browser calls production API, not localhost.
- [ ] Confirm frontend production build succeeds.
- [ ] Confirm Render backend starts.
- [ ] Confirm /api/health returns OK.
- [ ] Confirm production CORS_ORIGINS.
- [ ] Confirm Supabase environment variables.
- [ ] Confirm no service-role secret is exposed to frontend.
- [ ] Confirm Supabase RLS.
- [ ] Confirm PostGIS geometry storage.
- [ ] Confirm deployed AI dependencies/model artifacts.
- [ ] Confirm uploaded files can be processed in the deployment instance.
- [ ] Confirm the ephemeral-filesystem limitation is understood.
- [ ] If production persistence is required, verify durable object storage before claiming production readiness.

## 11. Exact SIH Demo Flow
- [ ] Login
- [ ] Create Project
- [ ] Create Survey
- [ ] Upload Orthomosaic
- [ ] Validate
- [ ] Start AI Analysis
- [ ] Show Processing
- [ ] Display Orthomosaic
- [ ] Display AI Features
- [ ] Display Candidate Parcels
- [ ] Display Reference Parcels
- [ ] Select Parcel
- [ ] Show Area
- [ ] Show Review Priority
- [ ] Show Validation Issues
- [ ] Show Reference Comparison
- [ ] Edit Boundary
- [ ] Undo
- [ ] Redo
- [ ] Save
- [ ] Accept or Request Field Verification
- [ ] Show Final Map
- [ ] Export GeoJSON
- [ ] Generate PDF Report
- [ ] Verify final export matches reviewed state.

## Sign-off
- [ ] Automated backend tests executed successfully.
- [ ] Frontend production build executed successfully.
- [ ] Live Supabase workflow executed successfully.
- [ ] Live Render deployment executed successfully.
- [ ] Complete SIH demo executed successfully.
- [ ] No release-blocking error remains.
- [ ] Only after all required checks pass: CERTIFY DEMO READY.