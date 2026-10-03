# SahiNaksha — Current Implementation Status

Date: 2026-10-03
Branch audited: `main`
Repository: `Syed-Sameer13/SahiNakshaDemo`

## Architecture audited

```
React + Leaflet
      ↓
FastAPI
      ↓
AI + OpenCV + GIS + validation
      ↓
Supabase/PostGIS schema (defined; not wired into the current analysis API)
      ↓
GeoJSON / browser download
```

No Node/Express layer is present and none was introduced.

## Working / implemented

### Frontend
- React + Vite application is present.
- Leaflet / React-Leaflet map workflow is implemented.
- Upload flow supports imagery plus optional reference parcels, DSM and ground truth.
- Local analysis history is implemented.
- GIS layer toggles are implemented.
- Feature selection and attribute editing are implemented.
- Polygon vertex dragging, add/delete vertex, undo/redo and reset are implemented.
- Manual polygon drawing is implemented.
- Review decisions are stored locally in browser storage.
- Final reviewed GeoJSON download is implemented.
- Supabase authentication gate is implemented when Supabase environment variables are configured.

Primary files:
- `frontend/src/App.jsx`
- `frontend/src/components/AuthGate.jsx`
- `frontend/src/components/UploadPanel.jsx`
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/lib/supabase.js`
- `frontend/src/styles.css`
- `frontend/vite.config.js`

### Backend
- FastAPI application and CORS middleware are implemented.
- `GET /` and `GET /health` are implemented.
- `POST /analyze` accepts image, reference parcel, ground-truth and DSM files.
- Disk-backed prototype analysis storage is implemented.
- `GET /analysis/{analysis_id}`
- `GET /analysis/{analysis_id}/metrics`
- `GET /analysis/{analysis_id}/export`
- Upload and output directories are created automatically.

Primary files:
- `backend/app/main.py`
- `backend/app/routes.py`
- `backend/app/services/storage.py`
- `backend/app/services/export_service.py`

### AI / image processing
- Custom YOLO segmentation integration exists and is preferred when `backend/models/sahinaksha_seg.pt` is available.
- Lightweight RandomForest pixel segmentation integration exists.
- HOTOSM ONNX building segmentation integration exists when its model artifact is supplied.
- Optional SAM integration exists.
- OpenCV fallback building/road extraction exists.

Primary files:
- `backend/app/services/yolo_segmentation.py`
- `backend/app/services/trained_segmentation.py`
- `backend/app/services/hotosm_building_segmentation.py`
- `backend/app/services/ai_segmentation.py`
- `backend/app/services/opencv_analysis.py`
- `backend/app/services/model_router.py`

### GIS / validation
- Reference parcel loading and image-edge refinement exist.
- Image-local normalized coordinates (0..100) are used by the current MVP.
- Topology repair and overlap handling exist.
- Geometry validation exists.
- Area metrics support valid projected/geographic CRSs and explicitly avoid pretending image-local units are m².
- Deterministic review-priority scoring exists.
- Optional ground-truth evaluation exists.

Primary files:
- `backend/app/services/cadastral_engine.py`
- `backend/app/services/topology_engine.py`
- `backend/app/services/validation.py`
- `backend/app/services/area_metrics.py`
- `backend/app/services/review_score.py`
- `backend/app/services/metrics.py`

### Database / authentication
- Supabase/PostGIS schema is defined in `supabase/schema.sql`.
- Tables and RLS policies are defined for projects, surveys, parcels and validation issues.
- Frontend Supabase email/password authentication is implemented.
- The current `/analyze` API still uses filesystem/in-memory analysis persistence rather than writing analysis results into Supabase/PostGIS.

## Partially implemented

- Real CRS-aware orthomosaic ingestion: the current parcel refinement expects image-local normalized coordinates and does not transform arbitrary lon/lat GeoJSON into the image coordinate system.
- Cadastral refinement: existing GIS parcels can be edge-refined, but authoritative survey/GNSS/field integration is not implemented.
- DSM: accepted as an aligned PNG/JPG grayscale raster and used as relative-height evidence; true geospatial raster/GeoTIFF handling is not implemented.
- Accuracy evaluation: ground-truth comparison exists, but the implementation is a simple IoU matching metric rather than a full production evaluation suite.
- Human review persistence: geometry/attributes/review decisions are persisted in browser localStorage, not yet synchronized to Supabase/PostGIS.
- PDF/report generation: no dedicated backend PDF reporting service is present in the current tree.
- HOTOSM/SAM/custom model artifacts: runtime integrations are present, but the large model files are external/local and are not committed.
- Deployment: `render.yaml` defines separate frontend and backend Render services, but repository CI verification is absent.

## Broken / fixed in this stabilization pass

### Source corruption
Literal escaped newline sequences had accidentally been embedded in executable source.

Fixed files:
- `backend/app/services/trained_segmentation.py`
- `backend/app/services/yolo_segmentation.py`
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/UploadPanel.jsx`

Examples included broken forms such as:
- Python: `cv2.arcLength(... )\\n`
- Python: `model.predict(\\n ... )`
- JSX: state declarations containing literal `\\n`

These were converted back to real source newlines without changing intended functionality.

### Parcel pipeline hardening
`analysis.py` could reach topology processing with no `parcels` key when an AI/OpenCV path produced no parcel layer. It is now guarded with an empty FeatureCollection before topology processing.

## Remaining blockers

1. **Model artifact integrity:** `backend/models/sahinaksha_pixel_model.joblib` is currently 1 byte in Git, so the committed artifact is not a usable trained model. A valid trained model must be supplied locally or regenerated from labelled data.
2. **Custom YOLO artifact:** `backend/models/sahinaksha_seg.pt` is not present in the repository tree. YOLO integration therefore cannot be considered available from the repository alone.
3. **HOTOSM model artifact:** `backend/models/hotosm_dinov3s_buildings.onnx` is not present in the repository tree.
4. **Supabase/PostGIS runtime integration:** schema/policies exist, but the current analysis route does not persist projects/surveys/parcels/validation issues to Supabase.
5. **Georeferencing:** arbitrary GeoJSON/GeoTIFF/orthomosaic CRS transformation is not implemented in the current MVP.
6. **Production report export:** current export is GeoJSON. A dedicated PDF/report service is not present.
7. **Automated CI:** there are currently no GitHub Actions workflow runs for this repository; verification must therefore be performed locally or via deployment checks.
8. **End-to-end live verification:** repository inspection alone cannot honestly certify `npm install`, `npm run build`, `python -m compileall app`, a live FastAPI process, or browser-level frontend/backend communication. Those commands require a runnable checkout/environment.

## Duplicate / obsolete implementation notes

The repository intentionally contains multiple AI providers and a mock analysis module. They should not be deleted solely from naming:
- `mock_analysis.py`
- `opencv_analysis.py`
- `ai_segmentation.py`
- `trained_segmentation.py`
- `yolo_segmentation.py`
- `hotosm_building_segmentation.py`

The active runtime selector is `model_router.py`, so provider removal should only happen after confirming no documentation, tests or deployment path depends on it.

## Files changed in this stabilization pass

- `backend/app/services/trained_segmentation.py`
- `backend/app/services/yolo_segmentation.py`
- `backend/app/services/analysis.py`
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/UploadPanel.jsx`
- `docs/current-implementation-status.md`

## Verification commands to run from the repository checkout

Backend:

```bash
cd backend
python -m compileall app
uvicorn app.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
```

Frontend:

```bash
cd frontend
npm install
npm run build
npm run dev
```

Frontend/backend communication:

```bash
# set VITE_API_URL in frontend/.env.local when backend is not on the default URL
curl http://127.0.0.1:8000/health
```

Then run one complete image analysis from the UI and verify the returned analysis is rendered in the Leaflet workspace.

## Current conclusion

The repository has a coherent prototype architecture and substantial functionality already implemented. The immediate stabilization work was source-corruption repair plus a small parcel-pipeline guard. The main blockers are missing/invalid model artifacts, lack of runtime Supabase persistence, lack of general georeferencing, and the fact that this GitHub-only audit cannot claim local build/start results without actually executing the checkout.
