# SahiNaksha GIS / Cadastral Methodology

## Scope

SahiNaksha produces preliminary cadastral candidate geometry for surveyor review. It does not determine legal ownership, title, or authoritative cadastral boundaries from AI imagery.

The processing combines AI physical-feature evidence, existing reference GIS when available, raster georeferencing and CRS information, geometric relationships, topology/geometry rules, deterministic validation, and human surveyor review.

A building footprint is never automatically treated as a parcel boundary.

## GIS processing pipeline

Raster / orthomosaic → raster metadata → AI feature evidence → vector polygons → geometry repair → reference GIS alignment → candidate parcel generation → candidate/reference comparison → topology validation → area/perimeter metrics → review-priority scoring → human surveyor editing and decision.

## Raster metadata

When rasterio is available, the engine extracts CRS, affine transform, bounds, pixel resolution, width, height, band count, data type, and georeferencing availability.

For ordinary JPG/PNG files without embedded georeferencing, CRS/transform are recorded as unavailable rather than invented.

### Pixel/map conversion

If a valid affine transform and CRS exist, pixel coordinates can be converted to raster CRS coordinates and map coordinates can be converted back to pixel coordinates.

## Geometry repair

Candidate and reference polygons are normalized by rejecting empty geometry, repairing invalid/self-intersecting polygons, removing tiny geometry, normalizing polygon output, optionally simplifying with topology preservation, and avoiding duplicate/near-identical candidate geometry.

Geometry repair does not make the result legally authoritative.

## Candidate parcel generation

### With reference GIS

Existing reference parcels are the primary spatial framework. The engine loads reference geometry, reads its CRS, reprojects it to the raster CRS when both CRSs are known, attaches intersecting AI building evidence, preserves reference identifiers, and sends the candidates through topology, validation, metrics, and human review.

### Without reference GIS

The engine may generate coarse preliminary evidence blocks from spatially separated AI building footprints. These are synthetic review candidates only and are explicitly marked as non-legal.

## Reference comparison

For each candidate, the engine selects the reference feature with the highest IoU and calculates candidate area, reference area, absolute area difference, percentage area difference, intersection area, IoU, and a symmetric boundary Hausdorff-distance proxy.

Discrepancy statuses are MATCH, MINOR_DISCREPANCY, MAJOR_DISCREPANCY, and NO_REFERENCE. These are review classifications, not legal conclusions.

## Area and perimeter rules

For a projected CRS whose linear unit is metres, area_sq_m and perimeter_m are reported.

For geographic latitude/longitude CRS, source coordinate units are not labelled as square metres.

If CRS is absent, area_sq_m and perimeter_m are null and no fake square-metre value is generated.

## Supported reference formats

The current cadastral reference loader directly supports GeoJSON and GeoJSON FeatureCollection. Shapefile/GeoPackage support is not silently claimed as implemented; they require a dedicated reader/dependency and CRS handling before acceptance.

Raster metadata uses rasterio when available; ordinary RGB JPG/PNG processing continues through OpenCV.

## Parcel attributes

Candidate parcels can contain parcel_id, parcel_area, parcel_perimeter, area_sq_m, perimeter_m, geometry_valid, source, reference_available, reference_parcel_id, ai_evidence, ai_evidence_feature_count, ai_evidence_overlap_area, intersection_area, intersection_over_union, absolute_area_difference, percentage_area_difference, boundary_displacement, discrepancy_status, review_priority, review_required, and legal_cadastral_boundary.

AI confidence is never invented by the GIS engine.

## Review priority

Review priority increases for invalid geometry, major reference discrepancy, low reference overlap, no reference framework, and evidence ambiguity. It is a deterministic prioritization aid, not a probability of correctness.

## Important limitations

1. RGB imagery does not establish land ownership.
2. Building footprints are physical structures, not legal parcels.
3. Roads, vegetation, walls, shadows, and image edges can be imperfect evidence.
4. Preliminary candidates may differ from true cadastral boundaries.
5. Reference GIS may itself be outdated or inaccurate.
6. Missing CRS prevents reliable real-world area reporting.
7. Geographic CRS is not a metre-based projected coordinate system.
8. Human surveyor review remains mandatory.
9. Final authoritative cadastral geometry must come from the applicable official survey/cadastral process.

## Tests

backend/tests/test_cadastral_engine.py covers valid polygons, invalid polygons, overlaps, empty geometry, missing CRS, geographic CRS, projected CRS, pixel/map round trips, and explicit non-legal AI candidate blocks.

Passing these tests demonstrates computational behavior, not cadastral accuracy.