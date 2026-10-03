# SahiNaksha API Contract

This contract documents the API that exists in the repository today. Planned endpoints are separated from implemented endpoints.

Base URL in local development:

```
http://127.0.0.1:8000
```

## 1. GET /

Implemented.

Response:

```json
{
  "name": "SahiNaksha API",
  "status": "running",
  "model": "sahinaksha_pixel_model | fallback"
}
```

The model value only indicates whether the configured pixel-model path exists; it does not prove that the artifact is valid or loadable.

## 2. GET /health

Implemented.

Example response:

```json
{
  "status": "ok",
  "service": "SahiNaksha API",
  "trained_model": {
    "available": true,
    "path": "sahinaksha_pixel_model.joblib"
  }
}
```

`available` currently means the configured file path exists.

## 3. POST /analyze

Implemented.

Content type:
- `multipart/form-data`

Fields:

| Field | Required | Current accepted type | Meaning |
|---|---|---|---|
| `file` | yes | JPG/JPEG/PNG | Input image |
| `reference_parcels` | no | JSON/GeoJSON | Existing parcel reference |
| `ground_truth` | no | JSON/GeoJSON | Evaluation reference |
| `dsm` | no | JPG/JPEG/PNG | Aligned grayscale height evidence |

Current limits:
- Image MIME type must be `image/jpeg` or `image/png`.
- Each uploaded file is limited to 20 MB.
- Reference parcel input is currently expected in image-local normalized coordinates 0..100 when used for refinement.
- General georeferenced GeoTIFF/CRS transformation is not currently implemented.

### Success response

Status: `200`

Representative structure:

```json
{
  "analysis_id": "uuid-like-hex",
  "status": "completed",
  "original_image_url": "/uploads/<filename>",
  "buildings": {"type": "FeatureCollection", "features": []},
  "roads": {"type": "FeatureCollection", "features": []},
  "parcels": {"type": "FeatureCollection", "features": []},
  "analysis_mode": "ai_segmentation | trained_segmentation | opencv_fallback",
  "ai_engine": {},
  "cadastral_mode": "drone_refined_existing_gis | feature_evidence_only | preliminary_feature_extraction",
  "validation": {},
  "topology_stats": {},
  "evaluation": {}
}
```

The exact feature properties depend on the selected AI/GIS path.

### Errors

- `400`: unsupported file type, empty file, oversized file, invalid input, or processing ValueError.
- `500`: unexpected analysis pipeline failure.

## 4. GET /analysis/{analysis_id}

Implemented.

Returns the stored analysis payload.

Storage lookup order:
1. in-memory `ANALYSES`
2. disk-backed `AnalysisStore`

Returns:
- `200` if found.
- `404` if not found.

## 5. GET /analysis/{analysis_id}/metrics

Implemented.

Returns derived metrics including:
- analysis mode,
- AI engine,
- cadastral mode,
- topology statistics,
- validation statistics,
- parcel count,
- mean review score,
- total area when available,
- area summary,
- review summary,
- ground-truth evaluation.

This endpoint does not currently read metrics from Supabase/PostGIS.

## 6. GET /analysis/{analysis_id}/export

Implemented.

Returns:
- media type: `application/geo+json`
- attachment filename: `sahinaksha-{analysis_id}.geojson`

The export is the stored analysis payload serialized as JSON/GeoJSON.

## 7. Authentication

Frontend authentication exists through Supabase Auth in `AuthGate.jsx`.

The current FastAPI endpoints do not validate a Supabase access token or map requests to a Supabase project owner.

Therefore:
- frontend login exists;
- backend API authorization is **not yet implemented**.

This distinction is intentional and important.

## 8. Survey/project APIs

Not implemented.

There are currently no backend endpoints for:
- `POST /projects`
- `GET /projects`
- `POST /surveys`
- project ownership administration
- review persistence
- audit logs

These should be added incrementally when Supabase runtime persistence is implemented.

## 9. Administrator APIs

Not implemented.

There are no current endpoints for:
- user management,
- project administration,
- processing dashboard,
- audit/review monitoring.

## 10. Future API contract direction

When persistence is implemented, prefer additive endpoints such as:

```
POST   /projects
GET    /projects
GET    /projects/{project_id}
POST   /projects/{project_id}/surveys
GET    /surveys/{survey_id}
POST   /surveys/{survey_id}/process
GET    /surveys/{survey_id}/status
GET    /surveys/{survey_id}/review
POST   /surveys/{survey_id}/review
GET    /surveys/{survey_id}/export
```

These are planned contracts, not current APIs.
