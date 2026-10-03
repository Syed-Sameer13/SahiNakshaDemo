import os
import cv2
import numpy as np
from shapely.geometry import Polygon
from .geojson_service import feature_collection


def _scale(point, width, height):
    x, y = point
    return [round(x * 100.0 / width, 3), round(100.0 - y * 100.0 / height, 3)]


def _vegetation_mask(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    b, g, r = cv2.split(image.astype(np.float32))
    exg = 2 * g - r - b
    hue = cv2.inRange(hsv, np.array([28, 30, 15]), np.array([100, 255, 255]))
    mask = cv2.bitwise_and(hue, (exg > 5).astype(np.uint8) * 255)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)


def _sam_generator():
    if os.getenv("SAHINAKSHA_ENABLE_SAM", "1") != "1":
        return None, "SAM disabled"

    default_checkpoint = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "models", "sam_vit_b_01ec64.pth")
    )
    checkpoint = os.getenv("SAHINAKSHA_SAM_CHECKPOINT", default_checkpoint)
    model_type = os.getenv("SAHINAKSHA_SAM_MODEL_TYPE", "vit_b")

    if not checkpoint or not os.path.exists(checkpoint):
        return None, f"SAM checkpoint missing: {checkpoint}"

    try:
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
        model = sam_model_registry[model_type](checkpoint=checkpoint)
        generator = SamAutomaticMaskGenerator(
            model=model,
            points_per_side=int(os.getenv("SAHINAKSHA_SAM_POINTS_PER_SIDE", "24")),
            pred_iou_thresh=float(os.getenv("SAHINAKSHA_SAM_PRED_IOU", "0.88")),
            stability_score_thresh=float(os.getenv("SAHINAKSHA_SAM_STABILITY", "0.92")),
            box_nms_thresh=0.55,
            crop_n_layers=2,
            crop_n_points_downscale_factor=2,
            min_mask_region_area=300,
        )
        return generator, "SAM"
    except Exception as exc:
        return None, f"SAM unavailable: {exc}"


def _mask_iou(a, b):
    inter = cv2.countNonZero(cv2.bitwise_and(a, b))
    union = cv2.countNonZero(cv2.bitwise_or(a, b))
    return inter / max(union, 1)


def _polygon_from_contour(contour, width, height, epsilon=0.009):
    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        return None, None
    approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
    if len(approx) < 4 or len(approx) > 18:
        return None, None
    coords = [_scale(tuple(p[0]), width, height) for p in approx]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    poly = Polygon(coords)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon":
        return None, None
    return approx, poly


def _geometry_metrics(contour):
    area = max(float(cv2.contourArea(contour)), 1.0)
    perimeter = max(float(cv2.arcLength(contour, True)), 1.0)
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1.0)
    solidity = area / hull_area
    rect = cv2.minAreaRect(contour)
    rw, rh = rect[1]
    rectangularity = area / max(float(rw * rh), 1.0)
    x, y, w, h = cv2.boundingRect(contour)
    extent = area / max(float(w * h), 1.0)
    aspect = max(w, h) / max(1.0, min(w, h))
    return solidity, rectangularity, extent, aspect


def _edge_support(image, contour):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 40, 120)
    ring = np.zeros_like(edges)
    cv2.drawContours(ring, [contour], -1, 255, 2)
    return cv2.countNonZero(cv2.bitwise_and(edges, ring)) / max(cv2.countNonZero(ring), 1)


def _candidate_from_mask(image, item, vegetation):
    height, width = image.shape[:2]
    image_area = width * height
    mask = item["segmentation"].astype(np.uint8) * 255
    area = int(item.get("area", cv2.countNonZero(mask)))

    if area < max(250, image_area * 0.00035) or area > image_area * 0.12:
        return None

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < max(220, image_area * 0.0003):
        return None

    x, y, bw, bh = cv2.boundingRect(contour)
    touches = int(x <= 1) + int(y <= 1) + int(x + bw >= width - 1) + int(y + bh >= height - 1)
    if touches >= 2:
        return None

    _, polygon = _polygon_from_contour(contour, width, height)
    if polygon is None:
        return None

    vegetation_ratio = cv2.countNonZero(cv2.bitwise_and(mask, vegetation)) / max(area, 1)
    solidity, rectangularity, extent, aspect = _geometry_metrics(contour)
    edge_support = _edge_support(image, contour)

    if vegetation_ratio > 0.30 or aspect > 5.0:
        return None
    if solidity < 0.60 or rectangularity < 0.40 or extent < 0.26:
        return None

    model_score = 0.5 * float(item.get("predicted_iou", 0.5)) + 0.5 * float(item.get("stability_score", 0.5))
    geometry_score = 0.30 * rectangularity + 0.25 * solidity + 0.20 * extent + 0.25 * edge_support
    score = 0.55 * model_score + 0.45 * geometry_score - 0.25 * vegetation_ratio

    if score < 0.55:
        return None

    return {"mask": mask, "polygon": polygon, "bbox": (x, y, x + bw, y + bh),
            "score": float(score), "area": float(cv2.contourArea(contour)),
            "metrics": {"vegetation_ratio": round(float(vegetation_ratio), 2),
                        "rectangularity": round(float(rectangularity), 2),
                        "edge_support": round(float(edge_support), 2),
                        "solidity": round(float(solidity), 2)}}


def _nms_candidates(candidates):
    candidates.sort(key=lambda c: (c["score"], c["area"]), reverse=True)
    kept = []
    for candidate in candidates:
        if any(_mask_iou(candidate["mask"], existing["mask"]) > 0.45 or
               candidate["polygon"].intersection(existing["polygon"]).area / max(candidate["polygon"].area, 1e-6) > 0.80
               for existing in kept):
            continue
        kept.append(candidate)
    return kept


def _buildings_from_candidates(candidates):
    features = []
    for index, c in enumerate(candidates[:40], start=1):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in c["polygon"].exterior.coords]]},
            "properties": {
                "building_id": f"B-{index:03d}",
                "feature_type": "building_footprint",
                "confidence": round(min(0.97, max(0.50, c["score"])), 2),
                "pixel_area": round(c["area"], 1),
                "review_required": True,
                "source_model": "segment-anything",
                **c["metrics"],
            },
        })
    return feature_collection(features)


def _extract_roads(image, vegetation):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 130)
    edges[vegetation > 0] = 0
    height, width = image.shape[:2]
    min_length = int(min(width, height) * 0.35)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=max(45, min_length // 3),
                            minLineLength=min_length, maxLineGap=18)
    if lines is None:
        return feature_collection([])
    features = []
    for x1, y1, x2, y2 in sorted(lines[:, 0, :].tolist(),
                                  key=lambda p: np.hypot(p[2]-p[0], p[3]-p[1]), reverse=True):
        length = float(np.hypot(x2-x1, y2-y1))
        if length < min_length:
            continue
        coords = [_scale((x1, y1), width, height), _scale((x2, y2), width, height)]
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                         "properties": {"road_id": f"R-{len(features)+1:03d}",
                                        "feature_type": "road_evidence",
                                        "confidence": round(min(0.85, 0.45 + length / max(width, height)), 2),
                                        "review_required": True}})
        if len(features) >= 5:
            break
    return feature_collection(features)


def run_ai_segmentation(image_path):
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Unable to read image for AI segmentation.")

    generator, status = _sam_generator()
    if generator is None:
        return None, {"provider": "segment_anything", "status": status}

    vegetation = _vegetation_mask(image)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    masks = generator.generate(rgb)
    candidates = _nms_candidates([
        c for item in masks
        if (c := _candidate_from_mask(image, item, vegetation)) is not None
    ])
    buildings = _buildings_from_candidates(candidates)
    roads = _extract_roads(image, vegetation)

    return {"buildings": buildings, "roads": roads,
            "parcels": feature_collection([])}, {
        "provider": "segment_anything",
        "status": "ready",
        "raw_masks": len(masks),
        "accepted_buildings": len(buildings["features"]),
        "strategy": "standalone_sam",
    }
