# SahiNaksha Testing Strategy

## Purpose

Validation and review tests verify deterministic behavior and explainability. They do not prove cadastral accuracy or legal correctness.

## Automated tests

### GIS / geometry

backend/tests/test_cadastral_engine.py covers valid polygon metrics, invalid/self-intersecting polygon repair, candidate/reference comparison, empty geometry, missing CRS, geographic CRS area semantics, projected CRS metric area, pixel/map coordinate round trip, and explicit non-legal AI candidate blocks.

### Validation / review

backend/tests/test_validation.py covers required issue schema, polygon overlap, duplicate geometry, weak boundary evidence, area mismatch, reference mismatch, candidate outside reference boundary, building outside candidate parcel, deterministic review-priority labels, and explicit non-probability scoring.

## Required issue schema

Every generated validation issue contains issue ID, parcel ID, issue type, severity, description, evidence, status, and created timestamp.

Severity is limited to INFO, WARNING, ERROR, and CRITICAL.

## Manual acceptance checks

1. Invalid geometry produces a visible issue.
2. Overlapping parcels identify both affected parcel IDs.
3. Duplicate geometry is identified.
4. Tiny polygons are flagged as possible noise.
5. Reference area differences show the measured percentage.
6. Candidate geometry outside the reference is identified.
7. Buildings outside candidate coverage are flagged as evidence issues.
8. Weak boundary evidence is reported only when a real numeric signal exists.
9. The parcel panel explains review priority using concrete reasons.
10. The UI says Surveyor Review Required when issues need attention.
11. No UI or API field describes review priority as a probability of being wrong.

## Runtime verification note

Repository changes are source-reviewed through GitHub. If the project environment is not available for execution, do not claim that the automated suite passed. Run the suite locally before the SIH demonstration.

Recommended command: pytest backend/tests -q

## Testing limitations

Synthetic geometry tests validate computational rules. They do not measure model accuracy, survey accuracy, positional accuracy, or legal cadastral correctness. Real orthomosaics with known reference data should be used for final prototype validation.
