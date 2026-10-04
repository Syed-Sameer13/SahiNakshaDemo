"""HOTOSM DINOv3 building-footprint inference plus road/block evidence."""
from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from .geojson_service import feature_collection

MODEL_DEFAULT = Path(__file__).resolve().parents[2] / "models" / "hotosm_dinov3s_buildings.onnx"
MODEL_SIZE = 256
STRIDE_DEFAULT = 192
THRESHOLD_DEFAULT = 0.4371
MEAN = np.array([0.4296737853453577, 0.4001659668453235, 0.34333372802741474], dtype=np.float32)
STD = np.array([0.2056069389373208, 0.16738555558380538, 0.1598986422586595], dtype=np.float32)

_SESSION = None
_SESSION_PATH = None


def model_path() -> Path:
    """Resolve the HOTOSM ONNX artifact without silently pretending it exists."""
    configured = os.getenv("SAHINAKSHA_HOTOSM_MODEL")
    candidates = [
        Path(configured) if configured else None,
        MODEL_DEFAULT,
        Path(__file__).resolve().parents[2] / "models" / "model.onnx",
        Path.home() / ".cache" / "sahinaksha" / "hotosm_dinov3s_buildings.onnx",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file() and candidate.stat().st_size >= 128:
            return candidate
    return MODEL_DEFAULT


def _session():
    global _SESSION, _SESSION_PATH
    path = model_path()
    if not path.exists() or path.stat().st_size < 128:
        return None, (
            f"HOTOSM model missing or invalid: {path}. "
            "Download hotosm/dinov3s-buildings model.onnx and set "
            "SAHINAKSHA_HOTOSM_MODEL to its path."
        )
    if _SESSION is not None and _SESSION_PATH == str(path):
        return _SESSION, "ready"
    try:
        import onnxruntime as ort
        providers = ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        _SESSION = ort.InferenceSession(str(path), providers=providers)
        if not _SESSION.get_inputs():
            raise RuntimeError("HOTOSM ONNX model exposes no inputs")
        _SESSION_PATH = str(path)
        return _SESSION, "MODEL_AVAILABLE"
    except Exception as exc:
        return None, f"HOTOSM model unavailable: {exc}"


def _prepare(tile: np.ndarray) -> np.ndarray:
    # Match HOTOSM/fAIr exactly: every inference window is resampled to
    # the native 256x256 model input. Do not zero-pad small uploads because
    # the black padding changes the image statistics and can suppress roofs.
    if tile.shape[:2] != (MODEL_SIZE, MODEL_SIZE):
        interpolation = cv2.INTER_CUBIC if tile.shape[0] < MODEL_SIZE or tile.shape[1] < MODEL_SIZE else cv2.INTER_AREA
        tile = cv2.resize(tile, (MODEL_SIZE, MODEL_SIZE), interpolation=interpolation)
    rgb = cv2.cvtColor(tile, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    rgb = (rgb - MEAN) / STD
    return np.transpose(rgb, (2, 0, 1))[None, ...].astype(np.float32)


def _predict_tile(session, tile: np.ndarray) -> np.ndarray:
    input_name = session.get_inputs()[0].name
    output = np.asarray(session.run(None, {input_name: _prepare(tile)})[0])
    if output.ndim == 4:
        logits = output[:, 0]
    elif output.ndim == 3:
        logits = output
    else:
        raise RuntimeError(f"Unexpected HOTOSM ONNX output shape: {output.shape}")
    return 1.0 / (1.0 + np.exp(-np.clip(logits[0], -30, 30)))


def _windows(height: int, width: int, stride: int):
    max_x = max(width - MODEL_SIZE, 0)
    max_y = max(height - MODEL_SIZE, 0)
    xs = list(range(0, max_x + 1, stride)) or [0]
    ys = list(range(0, max_y + 1, stride)) or [0]
    if xs[-1] != max_x:
        xs.append(max_x)
    if ys[-1] != max_y:
        ys.append(max_y)
    return [(x, y) for y in ys for x in xs]


def _polygon_features(mask: np.ndarray, width: int, height: int, prefix: str, feature_type: str, min_area: int = 150):
    binary = (mask.astype(np.uint8) * 255)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    features = []
    for idx, contour in enumerate(contours, 1):
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        
        rect = cv2.minAreaRect(contour)
        box_pts = cv2.boxPoints(rect)
        box_area = cv2.contourArea(box_pts)
        rectangularity = area / max(box_area, 1e-6) if box_area > 0 else 0
        
        if rectangularity >= 0.70 and feature_type == "building_footprint":
            points = []
            for p in box_pts:
                x, y = float(p[0]), float(p[1])
                points.append([round(float(np.clip(x * 100.0 / width, 0, 100)), 3), round(float(np.clip(100.0 - y * 100.0 / height, 0, 100)), 3)])
            if points[0] != points[-1]:
                points.append(points[0])
        else:
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, max(1.0, 0.015 * perimeter), True)
            if len(approx) < 3:
                approx = cv2.approxPolyDP(contour, max(0.6, 0.008 * perimeter), True)
            points = []
            for p in approx[:, 0, :]:
                x, y = float(p[0]), float(p[1])
                points.append([round(float(np.clip(x * 100.0 / width, 0, 100)), 3), round(float(np.clip(100.0 - y * 100.0 / height, 0, 100)), 3)])
            if points[0] != points[-1]:
                points.append(points[0])
                
        if len(points) < 4:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [points]},
            "properties": {
                f"{prefix}_id": f"{prefix[0].upper()}-{idx:03d}",
                "feature_type": feature_type,
                "review_required": True,
            },
        })
    return feature_collection(features)


def _building_geojson(mask: np.ndarray, width: int, height: int, probability: np.ndarray | None = None):
    fc = _polygon_features(mask, width, height, "building", "building_footprint", min_area=150)
    for f in fc["features"]:
        props = f["properties"]
        props.update({"source_model": "hotosm/dinov3s-buildings", "confidence_available": False})
        if probability is not None:
            try:
                from shapely.geometry import shape
                geom = shape(f["geometry"])
                # Convert normalized 0..100 polygon back to pixel bounds for a conservative mean.
                coords = np.array(f["geometry"]["coordinates"][0], dtype=np.float32)
                xs = np.clip((coords[:, 0] * width / 100.0).astype(int), 0, width - 1)
                ys = np.clip(((100.0 - coords[:, 1]) * height / 100.0).astype(int), 0, height - 1)
                x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
                local = probability[y0:y1 + 1, x0:x1 + 1]
                valid = local[local >= 0]
                if valid.size:
                    props["confidence"] = round(float(np.mean(valid)), 4)
                    props["confidence_available"] = True
            except Exception:
                pass
    return fc


def _road_mask(image: np.ndarray, building_mask: np.ndarray) -> np.ndarray:
    """Conservative RGB road/asphalt evidence; parking may also be included."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    neutral = ((s < 95) & (v > 55) & (v < 205)).astype(np.uint8) * 255
    dark_neutral = ((s < 120) & (gray > 45) & (gray < 185)).astype(np.uint8) * 255
    mask = cv2.bitwise_or(neutral, dark_neutral)
    vegetation = ((h >= 28) & (h <= 100) & (s > 45) & (v > 35)).astype(np.uint8) * 255
    mask[vegetation > 0] = 0
    building = cv2.dilate((building_mask.astype(np.uint8) * 255), np.ones((7, 7), np.uint8), iterations=1)
    mask[building > 0] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    h_img, w_img = mask.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    cleaned = np.zeros_like(mask)
    min_area = max(250, int(h_img * w_img * 0.00025))
    for label in range(1, n):
        area = stats[label, cv2.CC_STAT_AREA]
        w = stats[label, cv2.CC_STAT_WIDTH]
        h = stats[label, cv2.CC_STAT_HEIGHT]
        elongation = max(w, h) / max(1, min(w, h))
        if area >= min_area and (elongation >= 2.0 or area >= min_area * 4):
            cleaned[labels == label] = 255
    return cleaned > 0


def _road_geojson(mask: np.ndarray, width: int, height: int):
    fc = _polygon_features(mask, width, height, "road", "road_evidence", min_area=max(250, int(width * height * 0.0003)))
    for f in fc["features"]:
        f["properties"].update({"confidence": "heuristic_evidence", "source": "rgb_asphalt_road_extractor"})
    return fc


def _preliminary_blocks(road_mask: np.ndarray, building_mask: np.ndarray, width: int, height: int):
    """Create non-authoritative land blocks separated by detected road corridors."""
    separator = cv2.dilate((road_mask.astype(np.uint8) * 255), np.ones((17, 17), np.uint8), iterations=1)
    separator = cv2.bitwise_or(separator, cv2.dilate((building_mask.astype(np.uint8) * 255), np.ones((3, 3), np.uint8), iterations=1))
    land = np.where(separator > 0, 0, 255).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(land, 8)
    blocks = np.zeros_like(land)
    min_area = max(1200, int(width * height * 0.002))
    for label in range(1, n):
        area = stats[label, cv2.CC_STAT_AREA]
        touches_edge = (
            stats[label, cv2.CC_STAT_LEFT] == 0 or stats[label, cv2.CC_STAT_TOP] == 0 or
            stats[label, cv2.CC_STAT_LEFT] + stats[label, cv2.CC_STAT_WIDTH] >= width or
            stats[label, cv2.CC_STAT_TOP] + stats[label, cv2.CC_STAT_HEIGHT] >= height
        )
        if area >= min_area and not touches_edge:
            blocks[labels == label] = 1
    fc = _polygon_features(blocks, width, height, "parcel", "preliminary_parcel_block", min_area=min_area)
    for f in fc["features"]:
        f["properties"].update({"confidence": "heuristic_block", "legal_boundary": False, "review_required": True})
    return fc


def run_hotosm_building_segmentation(image_path: str):
    session, status = _session()
    if session is None:
        return None, {"provider": "hotosm_dinov3s_buildings", "status": status}
    image = cv2.imread(image_path)
    if image is None:
        return None, {"provider": "hotosm_dinov3s_buildings", "status": "unable to read image"}
    height, width = image.shape[:2]
    stride = int(os.getenv("SAHINAKSHA_HOTOSM_STRIDE", str(STRIDE_DEFAULT)))
    threshold = float(os.getenv("SAHINAKSHA_HOTOSM_THRESHOLD", str(THRESHOLD_DEFAULT)))
    if not 0.0 < threshold < 1.0:
        raise ValueError("SAHINAKSHA_HOTOSM_THRESHOLD must be between 0 and 1.")
    probability = np.zeros((height, width), dtype=np.float32)
    weights = np.zeros((height, width), dtype=np.float32)
    windows = _windows(height, width, stride)
    for x, y in windows:
        crop = image[y:min(y + MODEL_SIZE, height), x:min(x + MODEL_SIZE, width)]
        actual_h, actual_w = crop.shape[:2]
        # The official HOTOSM serving path resamples each RGB window to 256x256.
        # Resize the prediction back to the crop footprint before stitching.
        tile_prob = _predict_tile(session, crop)
        if tile_prob.shape != (actual_h, actual_w):
            tile_prob = cv2.resize(
                tile_prob,
                (actual_w, actual_h),
                interpolation=cv2.INTER_LINEAR,
            )
        probability[y:y + actual_h, x:x + actual_w] += tile_prob
        weights[y:y + actual_h, x:x + actual_w] += 1.0
    probability /= np.maximum(weights, 1.0)
    building_mask = probability >= threshold
    buildings = _building_geojson(building_mask, width, height, probability)
    roads_mask = _road_mask(image, building_mask)
    roads = _road_geojson(roads_mask, width, height)
    parcels = _preliminary_blocks(roads_mask, building_mask, width, height)
    return {"buildings": buildings, "roads": roads, "parcels": parcels}, {
        "provider": "hotosm_dinov3s_buildings", "status": "MODEL_AVAILABLE", "threshold": threshold,
        "stride": stride, "windows": len(windows), "accepted_buildings": len(buildings["features"]),
        "accepted_roads": len(roads["features"]), "preliminary_parcel_blocks": len(parcels["features"]),
        "parcel_mode": "preliminary_blocks_not_legal_cadastre",
        "model": str(model_path()),
        "confidence_available": any(f.get("properties", {}).get("confidence_available") for f in buildings["features"]),
        "input_size": [width, height],
        "native_model_size": MODEL_SIZE,
        "small_input_resampled": bool(width < MODEL_SIZE or height < MODEL_SIZE),
        "inference_note": "Windows are resized to the HOTOSM 256x256 input contract before prediction and resized back before mosaicking.",
    }
