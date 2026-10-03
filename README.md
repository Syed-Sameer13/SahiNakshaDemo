# SahiNaksha 🗺️

## AI-Assisted Urban Parcel Mapping and Cadastral Feature Extraction — SIH 2026 PS-26012

SahiNaksha is an SIH prototype for extracting building/road evidence from drone or orthomosaic imagery, refining GIS parcel information, validating geometry, and presenting the result in a WebGIS workflow.

## Advanced AI pipeline

```text
Orthomosaic / Drone RGB
        ↓
HOTOSM / DINOv3 tiled building segmentation
        ↓
Building candidate polygons
        ↓
Meta Segment Anything (SAM) boundary refinement
        ↓
Edge + geometry cleanup
        ↓
Topology validation
        ↓
Human review
        ↓
GeoJSON / WebGIS
```

### Models actually used

**1. HOTOSM / DINOv3 building model**

The repository already contains the ONNX inference implementation. It performs overlapping tiled inference, probability aggregation and building-mask extraction.

**2. Meta Segment Anything (SAM)**

SAM is used as a boundary-refinement model. HOTOSM proposes the building location; SAM supplies a sharper object boundary, and the refinement is constrained back to the HOTOSM candidate to avoid uncontrolled mask expansion.

The implementation automatically looks for:

```text
backend/models/sam_vit_b_01ec64.pth
```

or you can override it:

```bash
export SAHINAKSHA_SAM_CHECKPOINT=/absolute/path/to/checkpoint.pth
export SAHINAKSHA_SAM_MODEL_TYPE=vit_b
export SAHINAKSHA_ENABLE_SAM=1
```

Meta publishes the official ViT-B checkpoint from its Segment Anything repository. The project also supports the larger `vit_l` and `vit_h` checkpoint names through the same registry, but ViT-B is the practical local default because it is substantially smaller.

### Download the SAM checkpoint

From the backend directory:

```bash
python scripts/download_sam_checkpoint.py
```

Then verify:

```bash
ls -lh models/sam_vit_b_01ec64.pth
```

The checkpoint is intentionally not committed to Git because it is a large binary model file.

### Install and run

```bash
cd ~/Documents/SahiNakshaDemo
source venv/bin/activate

cd backend
pip install -r requirements.txt
python scripts/download_sam_checkpoint.py

export SAHINAKSHA_ENABLE_SAM=1
python -m uvicorn app.main:app --reload
```

In another terminal:

```bash
cd ~/Documents/SahiNakshaDemo/frontend
npm install
npm run dev
```

### Model selection behavior

The runtime order is deliberately:

```text
HOTOSM / DINOv3
      ↓
SAM boundary refinement
      ↓
standalone SAM fallback
      ↓
custom YOLO compatibility fallback
      ↓
trained pixel-model compatibility fallback
      ↓
OpenCV fallback
```

Custom models are therefore **not** the preferred inference path.

## Cadastral accuracy rule

A detected building footprint is not a legal property boundary. RGB imagery alone cannot establish ownership. When authoritative parcel GIS is supplied, SahiNaksha can refine and validate those existing boundaries using image evidence. Final cadastral boundaries require authoritative GIS/survey evidence and human verification.

## Prototype limitations

Accuracy depends on image resolution, orthorectification, scene type, model checkpoint, shadows/vegetation, and available ground truth. The prototype reports model provenance and review status instead of claiming guaranteed cadastral accuracy.

For production GIS, add GeoTIFF CRS handling, DSM/DTM, GNSS/CORS, authoritative cadastral layers and field-survey integration.
