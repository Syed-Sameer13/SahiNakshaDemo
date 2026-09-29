# SahiNaksha 🗺️

## AI-Assisted Urban Parcel Mapping and Cadastral Feature Extraction — SIH 2026 PS-26012

SahiNaksha is an SIH prototype for extracting building/road evidence from drone or orthomosaic imagery, refining GIS parcel information, validating geometry, and presenting the result in a WebGIS workflow.

## Advanced prototype pipeline

```text
Orthomosaic / Drone RGB
        ↓
Tiled HOTOSM / DINOv3 building inference
        ↓
Building candidate masks
        ↓
SAM boundary refinement
        ↓
Edge-aware polygon cleanup
        ↓
GIS parcel/reference refinement (when authoritative GIS is supplied)
        ↓
Topology validation
        ↓
Land-use / feature attributes
        ↓
Human review
        ↓
GeoJSON / WebGIS
```

### Model strategy

The preferred runtime path is now **HOTOSM/DINOv3 building inference followed by SAM boundary refinement**.

- **HOTOSM/DINOv3**: semantic building-footprint candidate generation using tiled ONNX inference.
- **SAM**: boundary refinement constrained by the HOTOSM candidate, rather than accepting arbitrary scene masks.
- **Custom YOLO / pixel models**: retained only as compatibility fallbacks when the advanced pretrained pipeline is unavailable.

SAM requires a compatible checkpoint. Configure:

```bash
export SAHINAKSHA_ENABLE_SAM=1
export SAHINAKSHA_SAM_CHECKPOINT=/absolute/path/to/sam_vit_h_4b8939.pth
export SAHINAKSHA_SAM_MODEL_TYPE=vit_h
```

If SAM is not configured, HOTOSM still runs and the system reports that boundary refinement was skipped.

## Cadastral accuracy rule

A detected building footprint is **not** a legal property boundary. SahiNaksha therefore does not fabricate ownership boundaries from RGB pixels. When an existing cadastral/GIS parcel layer is available, the system can refine and validate it using image evidence. Final cadastral boundaries require authoritative GIS/survey evidence and human verification.

## Current GIS prototype

The WebGIS uses image-local normalized coordinates (0..100) for the prototype. Production deployment should add GeoTIFF CRS handling, DSM/DTM, GNSS/CORS, authoritative cadastral layers and field-survey integration.

## Local setup

```bash
cd backend
source ../venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The frontend can then be started from `frontend/` with `npm install && npm run dev`.

## Important prototype limitation

Model accuracy depends on the imagery, resolution, model checkpoint, scene type and available ground truth. The system should report model provenance and review status rather than claiming legal or guaranteed cadastral accuracy.
