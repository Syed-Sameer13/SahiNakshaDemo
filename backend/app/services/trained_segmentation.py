"""Lightweight trained RGB segmentation model for SahiNaksha.

This optional CPU-friendly model provides preliminary physical-feature masks.
It must not be treated as a legal cadastral/ownership boundary generator.
"""
from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np


def _default_model_path() -> Path:
    return Path(__file__).resolve().parents[2] / "models" / "sahinaksha_pixel_model.joblib"


def _features(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32) / 255.0
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32) / 255.0
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    blur = cv2.GaussianBlur(gray, (0, 0), 1.2)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, 3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, 3)
    edge = np.sqrt(gx * gx + gy * gy)
    exg = 2.0 * rgb[:, :, 1] - rgb[:, :, 0] - rgb[:, :, 2]
    yy, xx = np.mgrid[0:h, 0:w]
    xx = xx.astype(np.float32) / max(w - 1, 1)
    yy = yy.astype(np.float32) / max(h - 1, 1)
    return np.stack([
        rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2],
        hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2],
        lab[:, :, 0], lab[:, :, 1], lab[:, :, 2],
        gray, blur, edge, exg, xx, yy,
    ], axis=-1)


def _load_model():
    path = Path(os.getenv("SAHINAKSHA_PIXEL_MODEL_PATH", str(_default_model_path())))
    if not path.exists():
        return None, f"trained model not found: {path}"
    if path.stat().st_size < 128:
        return None, f"trained model artifact is empty or incomplete: {path}"
    try:
        import joblib
        bundle = joblib.load(path)
        return bundle["model"] if isinstance(bundle, dict) else bundle, f"loaded {path.name}"
    except Exception as exc:
        return None, f"trained model load failed: {exc}"


def _predict(model, image: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    h, w = image.shape[:2]
    f = _features(image).reshape(-1, 15)
    pred = np.empty((f.shape[0],), dtype=np.uint8)
    probabilities = np.full((f.shape[0],), np.nan, dtype=np.float32)
    classes = getattr(model, "classes_", None)
    building_index = None
    if classes is not None:
        for idx, cls in enumerate(classes):
            if int(cls) == 1:
                building_index = idx
                break

    for start in range(0, len(f), 50000):
        batch = f[start:start + 50000]
        pred[start:start + 50000] = model.predict(batch).astype(np.uint8)
        if building_index is not None and hasattr(model, "predict_proba"):
            try:
                probabilities[start:start + len(batch)] = model.predict_proba(batch)[:, building_index]
            except Exception:
                probabilities[start:start + len(batch)] = np.nan
    return pred.reshape(h, w), probabilities.reshape(h, w) if building_index is not None else None


def _cleanup(mask: np.ndarray, cls: int, min_area: int) -> np.ndarray:
    binary = (mask == cls).astype(np.uint8) * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    clean = np.zeros_like(binary)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            clean[labels == i] = 255
    return clean


def _polygon_features(binary, image_shape, feature_type, prefix, min_area, confidence_map=None, max_items=60):
    h, w = image_shape[:2]
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    features = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:max_items]:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, max(1.0, 0.006 * perimeter), True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        coords = [[round(float(x) * 100.0 / w, 3), round(100.0 - float(y) * 100.0 / h, 3)] for x, y in approx]
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        props = {
            f"{prefix}_id": f"{prefix[0].upper()}-{len(features)+1:03d}",
            "feature_type": feature_type,
            "pixel_area": round(area, 1),
            "review_required": True,
            "model_provider": "sahinaksha_trained_pixel_model",
            "confidence_available": False,
        }
        if confidence_map is not None:
            x, y, bw, bh = cv2.boundingRect(contour)
            local = confidence_map[y:y + bh, x:x + bw]
            valid = local[np.isfinite(local)]
            if valid.size:
                props["confidence"] = round(float(np.mean(valid)), 4)
                props["confidence_available"] = True
        features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]}, "properties": props})
    return features


def run_trained_segmentation(image_path: str):
    image = cv2.imread(image_path)
    if image is None:
        return None, {"provider": "trained_pixel_model", "status": "MODEL_UNAVAILABLE", "reason": "image read failed"}
    model, load_status = _load_model()
    if model is None:
        return None, {"provider": "trained_pixel_model", "status": "MODEL_UNAVAILABLE", "reason": load_status}

    h, w = image.shape[:2]
    min_building = max(80, int(h * w * 0.00015))
    min_road = max(120, int(h * w * 0.00020))
    labels, confidence_map = _predict(model, image)
    building_mask = _cleanup(labels, 1, min_building)
    road_mask = _cleanup(labels, 2, min_road)

    from .geojson_service import feature_collection
    buildings = feature_collection(_polygon_features(building_mask, image.shape, "building_footprint", "building", min_building, confidence_map, 60))
    roads = feature_collection(_polygon_features(road_mask, image.shape, "road_area", "road", min_road, None, 30))

    return {"buildings": buildings, "roads": roads, "parcels": feature_collection([])}, {
        "provider": "sahinaksha_trained_pixel_model",
        "status": "MODEL_AVAILABLE",
        "building_count": len(buildings["features"]),
        "road_count": len(roads["features"]),
        "input_size": [w, h],
        "classes": ["background", "building", "road"],
        "confidence_available": bool(confidence_map is not None and np.isfinite(confidence_map).any()),
        "message": load_status,
    }
