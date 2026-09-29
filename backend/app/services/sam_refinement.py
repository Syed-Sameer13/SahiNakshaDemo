"""Refine HOTOSM building candidates with SAM boundary masks.

HOTOSM/DINOv3 supplies the semantic building candidate. SAM is used only as a
boundary refiner, so the final footprint is constrained by the HOTOSM candidate
rather than accepting arbitrary SAM scene segments.
"""
from __future__ import annotations

import cv2
import numpy as np
from shapely.geometry import Polygon

from .ai_segmentation import _sam_generator


def _to_pixels(coords, width, height):
    pts = []
    for x, y in coords:
        px = int(round(float(x) * width / 100.0))
        py = int(round((100.0 - float(y)) * height / 100.0))
        pts.append([px, py])
    return np.asarray(pts, dtype=np.int32)


def _to_local(contour, width, height):
    points = []
    for p in contour[:, 0, :]:
        x, y = float(p[0]), float(p[1])
        points.append([round(x * 100.0 / width, 3), round(100.0 - y * 100.0 / height, 3)])
    if points and points[0] != points[-1]:
        points.append(points[0])
    return points


def _mask_iou(a, b):
    inter = cv2.countNonZero(cv2.bitwise_and(a, b))
    union = cv2.countNonZero(cv2.bitwise_or(a, b))
    return inter / max(union, 1)


def _candidate_score(mask, hotosm_mask, predicted_iou, stability):
    overlap = _mask_iou(mask, hotosm_mask)
    # Prefer masks that preserve the HOTOSM semantic candidate while using
    # SAM's sharper boundary. Model quality scores are supporting evidence.
    return 0.55 * overlap + 0.25 * float(predicted_iou) + 0.20 * float(stability)


def refine_hotosm_buildings(image_path: str, buildings: dict):
    generator, status = _sam_generator()
    if generator is None:
        return buildings, {
            "status": "skipped",
            "reason": status,
            "refined": 0,
            "strategy": "hotosm_only",
        }

    image = cv2.imread(image_path)
    if image is None:
        return buildings, {
            "status": "skipped",
            "reason": "unable to read image",
            "refined": 0,
            "strategy": "hotosm_only",
        }

    height, width = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Automatic SAM produces a scene-level mask set once. Each HOTOSM
    # candidate then selects the best compatible SAM mask inside its region.
    masks = generator.generate(rgb)
    refined_features = []
    refined_count = 0

    for feature in buildings.get("features", []):
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [[]])[0]
        if len(coords) < 4:
            refined_features.append(feature)
            continue

        hotosm_mask = np.zeros((height, width), dtype=np.uint8)
        polygon_points = _to_pixels(coords, width, height)
        cv2.fillPoly(hotosm_mask, [polygon_points], 255)

        x, y, bw, bh = cv2.boundingRect(polygon_points)
        pad = max(8, int(0.08 * max(bw, bh)))
        rx1, ry1 = max(0, x - pad), max(0, y - pad)
        rx2, ry2 = min(width, x + bw + pad), min(height, y + bh + pad)

        best = None
        best_score = 0.0
        for item in masks:
            segmentation = item.get("segmentation")
            if segmentation is None:
                continue
            mask = (segmentation.astype(np.uint8) * 255)
            candidate = np.zeros_like(mask)
            candidate[ry1:ry2, rx1:rx2] = mask[ry1:ry2, rx1:rx2]
            if cv2.countNonZero(candidate) == 0:
                continue

            score = _candidate_score(
                candidate,
                hotosm_mask,
                item.get("predicted_iou", 0.5),
                item.get("stability_score", 0.5),
            )
            overlap = _mask_iou(candidate, hotosm_mask)
            if overlap < 0.35 or score <= best_score:
                continue

            best = (candidate, item, overlap)
            best_score = score

        if best is None:
            refined_features.append(feature)
            continue

        candidate_mask, item, overlap = best
        # Keep only the SAM portion supported by the HOTOSM candidate plus a
        # small tolerance. This prevents SAM from expanding into nearby roofs.
        support = cv2.dilate(hotosm_mask, np.ones((7, 7), np.uint8), iterations=1)
        candidate_mask = cv2.bitwise_and(candidate_mask, support)

        contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            refined_features.append(feature)
            continue

        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < max(150, 0.0002 * width * height):
            refined_features.append(feature)
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, max(0.8, 0.006 * perimeter), True)
        if len(approx) < 4:
            refined_features.append(feature)
            continue

        local = _to_local(approx, width, height)
        polygon = Polygon(local)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty or polygon.geom_type != "Polygon":
            refined_features.append(feature)
            continue

        props = dict(feature.get("properties", {}))
        props.update({
            "source_model": "hotosm_dinov3s_buildings+sam_boundary_refinement",
            "boundary_refinement": "SAM",
            "sam_overlap": round(float(overlap), 3),
            "sam_predicted_iou": round(float(item.get("predicted_iou", 0.0)), 3),
            "sam_stability": round(float(item.get("stability_score", 0.0)), 3),
            "confidence": round(
                min(
                    0.99,
                    max(
                        0.50,
                        0.55 * best_score
                        + 0.45 * float(
                            props.get("confidence", 0.5)
                            if isinstance(props.get("confidence"), (int, float))
                            else 0.5
                        ),
                    ),
                ),
                3,
            ),
            "review_required": True,
        })
        refined_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [list(map(list, polygon.exterior.coords))],
            },
            "properties": props,
        })
        refined_count += 1

    return {
        "type": "FeatureCollection",
        "features": refined_features,
    }, {
        "status": "ready",
        "strategy": "hotosm_candidate_plus_sam_boundary_refinement",
        "raw_sam_masks": len(masks),
        "input_buildings": len(buildings.get("features", [])),
        "refined": refined_count,
    }
