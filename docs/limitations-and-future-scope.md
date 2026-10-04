# SahiNaksha Limitations and Future Scope

## Current limitations

1. SahiNaksha provides preliminary physical-feature and cadastral-candidate evidence. It does not determine legal ownership, title, or authoritative cadastral boundaries.
2. Building footprints are physical structures and must never be interpreted automatically as legal parcel boundaries.
3. Review priority is a deterministic triage indicator. It is not AI accuracy, confidence, probability of error, or a legal risk score.
4. Model confidence is used only when an installed model actually provides a numeric confidence signal. The system does not invent confidence for fallback or heuristic processing.
5. Boundary evidence is evaluated only when a measurable numeric signal is available.
6. Missing CRS prevents reliable real-world area/perimeter reporting.
7. Reference GIS may be outdated, incomplete, or inaccurate.
8. Reference mismatch does not prove that the candidate is wrong; it identifies a condition requiring investigation.
9. Gap detection depends on having a usable reference framework.
10. RGB imagery can be affected by shadows, occlusion, vegetation, roofs, image seams, resolution, and capture conditions.
11. GeoJSON reference input is supported by the current cadastral loader; Shapefile and GeoPackage are not silently treated as implemented.
12. The current API upload path accepts JPG/JPEG/PNG imagery. GeoTIFF support requires explicit upload and processing integration.
13. Automated validation can identify geometric inconsistencies, but it cannot replace field verification.

## Explainable review design

Each issue stores the evidence used to create it. Reviewers can filter issues by severity and inspect parcel-level reasons.

The review-risk indicator is deterministic. Validation severity, invalid geometry, reference mismatch, measured area discrepancy, measured boundary displacement, weak boundary evidence, and genuinely supplied model confidence each contribute bounded, documented review points.

The resulting priority is LOW, MEDIUM, HIGH, or CRITICAL. This ranking is for surveyor triage only.

## Future scope

### Stronger geospatial ingestion

GeoTIFF orthomosaic upload with CRS validation; Shapefile/GeoPackage ingestion; ground-control-point workflows; explicit datum and unit handling.

### Better boundary evidence

Learned boundary/edge models; stronger DINOv3/HOTOSM evidence; SAM refinement with calibrated source metrics; wall, fence, road-edge and terrain-boundary evidence; multi-source evidence fusion.

### Review workflow

Authenticated surveyor roles; server-side issue and review persistence; assignment queues; comments and evidence attachments; audit logs; parcel-by-parcel review sessions.

### Validation quality

Configurable thresholds per project; stronger gap/coverage analysis; topology rule configuration; spatial indexing for large datasets; calibrated evaluation against authoritative reference datasets.

### Accuracy evaluation

IoU and boundary-distance distributions; precision/recall for physical feature detection; held-out regional datasets; uncertainty calibration where model probabilities are genuinely available.

### Production hardening

Background processing for large orthomosaics; object storage; database-backed analysis jobs; authenticated API access; monitoring; structured logs; rate limiting; upload security.
