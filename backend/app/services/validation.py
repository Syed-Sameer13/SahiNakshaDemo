from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from shapely.geometry import shape
from shapely.ops import unary_union
from shapely import normalize


SEVERITIES = ("INFO", "WARNING", "ERROR", "CRITICAL")
OPEN_STATUSES = {"OPEN", "REVIEW_REQUIRED"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue(
    parcel_id: str,
    issue_type: str,
    severity: str,
    description: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "issue_id": f"VAL-{uuid4().hex[:12].upper()}",
        "parcel_id": str(parcel_id),
        "issue_type": issue_type,
        "severity": severity if severity in SEVERITIES else "WARNING",
        "description": description,
        "evidence": evidence,
        "status": "OPEN",
        "created_timestamp": _now(),
    }


def _geometry(feature: dict[str, Any]):
    try:
        geometry = feature.get("geometry")
        return shape(geometry) if geometry else None
    except Exception:
        return None


def _parcel_id(feature: dict[str, Any], fallback: str = "UNKNOWN") -> str:
    return str(feature.get("properties", {}).get("parcel_id") or feature.get("id") or fallback)


def _candidate_reference(reference_parcels: dict[str, Any] | None) -> list[tuple[str, Any]]:
    result = []
    for feature in (reference_parcels or {}).get("features", []):
        geom = _geometry(feature)
        if geom is not None and not geom.is_empty:
            result.append((_parcel_id(feature), geom))
    return result


def _safe_percentage(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def validate_parcels(
    feature_collection: dict[str, Any],
    buildings: dict[str, Any] | None = None,
    reference_parcels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run deterministic, evidence-backed parcel validation.

    This produces review issues, not an accuracy/probability estimate.
    Every issue is linked to a parcel ID and records the evidence used.
    """
    features = feature_collection.get("features", [])
    issues: list[dict[str, Any]] = []
    geometries: list[tuple[str, Any, dict[str, Any]]] = []
    duplicate_keys: dict[bytes, list[str]] = {}
    reference_geometries = _candidate_reference(reference_parcels)

    for feature in features:
        parcel_id = _parcel_id(feature)
        props = feature.setdefault("properties", {})
        geometry = _geometry(feature)

        if geometry is None:
            props["geometry_valid"] = False
            issues.append(_issue(parcel_id, "GEOMETRY_INVALID", "CRITICAL",
                                 "Parcel geometry could not be parsed.",
                                 {"geometry_present": bool(feature.get("geometry"))}))
            continue

        if geometry.is_empty:
            props["geometry_valid"] = False
            issues.append(_issue(parcel_id, "GEOMETRY_INVALID", "CRITICAL",
                                 "Parcel geometry is empty.",
                                 {"area": 0}))
            continue

        if not geometry.is_valid:
            props["geometry_valid"] = False
            reason = getattr(geometry, "is_valid_reason", None)
            description = "Parcel geometry is invalid."
            evidence = {"valid": False}
            if reason:
                evidence["reason"] = reason
            issues.append(_issue(parcel_id, "GEOMETRY_INVALID", "ERROR", description, evidence))

        if hasattr(geometry, "exterior") and not geometry.is_simple:
            issues.append(_issue(parcel_id, "SELF_INTERSECTION", "ERROR",
                                 "Parcel boundary contains a self-intersection or non-simple ring.",
                                 {"is_simple": bool(geometry.is_simple)}))

        if geometry.area <= 0:
            issues.append(_issue(parcel_id, "GEOMETRY_INVALID", "CRITICAL",
                                 "Parcel has zero or negative area.",
                                 {"area": float(geometry.area)}))

        if geometry.area < 25:
            issues.append(_issue(parcel_id, "TINY_NOISE_POLYGON", "WARNING",
                                 "Parcel is below the configured minimum area and may be noise.",
                                 {"area": float(geometry.area), "threshold": 25.0}))

        key = normalize(geometry).wkb
        duplicate_keys.setdefault(key, []).append(parcel_id)
        geometries.append((parcel_id, geometry, props))
        props["geometry_valid"] = bool(geometry.is_valid and not geometry.is_empty and geometry.area > 0)

    for ids in duplicate_keys.values():
        if len(ids) > 1:
            for parcel_id in ids:
                issues.append(_issue(parcel_id, "DUPLICATE_GEOMETRY", "ERROR",
                                     "Parcel geometry is identical to another candidate parcel.",
                                     {"duplicate_parcel_ids": [x for x in ids if x != parcel_id]}))

    for i, (left_id, left, _) in enumerate(geometries):
        for right_id, right, _ in geometries[i + 1:]:
            try:
                intersection = left.intersection(right)
                if not intersection.is_empty and intersection.area > 0.001:
                    issues.append(_issue(
                        left_id, "POLYGON_OVERLAP", "ERROR",
                        f"Parcel overlaps candidate {right_id}.",
                        {"other_parcel_id": right_id, "intersection_area": float(intersection.area)}
                    ))
                    issues.append(_issue(
                        right_id, "POLYGON_OVERLAP", "ERROR",
                        f"Parcel overlaps candidate {left_id}.",
                        {"other_parcel_id": left_id, "intersection_area": float(intersection.area)}
                    ))
            except Exception as exc:
                issues.append(_issue(left_id, "POLYGON_OVERLAP", "WARNING",
                                     "Overlap check could not be completed for this pair.",
                                     {"other_parcel_id": right_id, "error": str(exc)}))

    # Reference-based checks.
    for parcel_id, geometry, props in geometries:
        reference_id = props.get("reference_parcel_id")
        reference_geom = None

        if reference_id:
            reference_geom = next((g for rid, g in reference_geometries if rid == str(reference_id)), None)
        if reference_geom is None and reference_geometries:
            scored = [(geometry.intersection(g).area / geometry.union(g).area if not geometry.union(g).is_empty else 0, rid, g)
                      for rid, g in reference_geometries]
            if scored:
                _, reference_id, reference_geom = max(scored, key=lambda item: item[0])

        if reference_geom is not None:
            outside_area = geometry.difference(reference_geom).area
            if outside_area > 0.001:
                issues.append(_issue(
                    parcel_id, "CANDIDATE_OUTSIDE_REFERENCE", "ERROR",
                    "Candidate parcel extends outside its matched reference boundary.",
                    {"reference_parcel_id": reference_id, "outside_area": float(outside_area)}
                ))

            pct = _safe_percentage(props.get("percentage_area_difference"))
            if pct is not None and pct > 5:
                severity = "CRITICAL" if pct > 20 else "ERROR" if pct > 10 else "WARNING"
                issues.append(_issue(
                    parcel_id, "AREA_MISMATCH", severity,
                    f"Candidate area differs from the reference by {pct:.1f}%.",
                    {"reference_parcel_id": reference_id, "percentage_area_difference": pct}
                ))

            discrepancy = str(props.get("discrepancy_status", ""))
            if discrepancy in {"MINOR_DISCREPANCY", "MAJOR_DISCREPANCY"}:
                severity = "CRITICAL" if discrepancy == "MAJOR_DISCREPANCY" else "WARNING"
                issues.append(_issue(
                    parcel_id, "REFERENCE_MISMATCH", severity,
                    f"Reference comparison is classified as {discrepancy}.",
                    {
                        "reference_parcel_id": reference_id,
                        "discrepancy_status": discrepancy,
                        "intersection_over_union": props.get("intersection_over_union"),
                        "boundary_displacement": props.get("boundary_displacement"),
                    }
                ))

            displacement = _safe_percentage(props.get("boundary_displacement"))
            if displacement is not None and displacement > 0:
                issues.append(_issue(
                    parcel_id, "REFERENCE_BOUNDARY_DISPLACEMENT", "WARNING",
                    "Candidate and reference boundaries are spatially displaced.",
                    {"reference_parcel_id": reference_id, "boundary_displacement": displacement}
                ))

        elif reference_geometries:
            issues.append(_issue(
                parcel_id, "REFERENCE_MISMATCH", "ERROR",
                "No suitable reference parcel could be matched.",
                {"reference_count": len(reference_geometries)}
            ))

    # Gap detection: meaningful only when a reference framework exists.
    if reference_geometries and geometries:
        reference_union = unary_union([g for _, g in reference_geometries])
        candidate_union = unary_union([g for _, g, _ in geometries])
        gap_geom = reference_union.difference(candidate_union)
        if not gap_geom.is_empty and gap_geom.area > 0.001:
            for parcel_id, geometry, _ in geometries:
                local_gap = gap_geom.intersection(geometry.buffer(0.01))
                if not local_gap.is_empty and local_gap.area > 0.001:
                    issues.append(_issue(
                        parcel_id, "GAP_DETECTED", "WARNING",
                        "A gap exists between candidate coverage and the reference boundary near this parcel.",
                        {"gap_area": float(local_gap.area)}
                    ))
            if not any(i["issue_type"] == "GAP_DETECTED" for i in issues):
                nearest_id = min(geometries, key=lambda item: item[1].distance(gap_geom))[0]
                issues.append(_issue(
                    nearest_id, "GAP_DETECTED", "WARNING",
                    "A gap exists between candidate coverage and the reference boundary.",
                    {"gap_area": float(gap_geom.area)}
                ))

    # Building containment is evidence only; a building footprint is not a legal parcel.
    building_features = (buildings or {}).get("features", [])
    for building in building_features:
        building_geom = _geometry(building)
        if building_geom is None or building_geom.is_empty:
            continue
        containing = [
            (parcel_id, parcel_geom.intersection(building_geom).area / building_geom.area)
            for parcel_id, parcel_geom, _ in geometries
            if not parcel_geom.is_empty and parcel_geom.intersects(building_geom)
        ]
        if not containing:
            nearest_id = min(geometries, key=lambda item: item[1].distance(building_geom))[0] if geometries else "UNASSIGNED"
            issues.append(_issue(
                nearest_id, "BUILDING_OUTSIDE_PARCEL", "WARNING",
                "A detected building footprint does not intersect any candidate parcel.",
                {"building_id": building.get("properties", {}).get("building_id"), "assigned_parcel_id": nearest_id}
            ))
        elif max(x[1] for x in containing) < 0.5:
            best_id, overlap_fraction = max(containing, key=lambda x: x[1])
            issues.append(_issue(
                best_id, "BUILDING_OUTSIDE_PARCEL", "WARNING",
                "A detected building has weak spatial containment within candidate parcels.",
                {"building_id": building.get("properties", {}).get("building_id"), "overlap_fraction": round(overlap_fraction, 4)}
            ))

    # Boundary evidence is only evaluated when a real numeric evidence value exists.
    for parcel_id, _, props in geometries:
        evidence = props.get("boundary_evidence")
        if isinstance(evidence, (int, float)):
            value = float(evidence)
            if value < 0.6:
                issues.append(_issue(
                    parcel_id, "WEAK_BOUNDARY_EVIDENCE", "WARNING",
                    "Available boundary evidence is weak and should be checked against imagery or field evidence.",
                    {"boundary_evidence": value, "threshold": 0.6}
                ))

    severity_counts = {severity: sum(1 for i in issues if i["severity"] == severity) for severity in SEVERITIES}
    status_counts = {}
    for issue in issues:
        status_counts[issue["status"]] = status_counts.get(issue["status"], 0) + 1

    for feature in features:
        props = feature.setdefault("properties", {})
        parcel_id = _parcel_id(feature)
        parcel_issues = [i for i in issues if i["parcel_id"] == parcel_id]
        props["validation_issue_count"] = len(parcel_issues)
        props["validation_status"] = "ERROR" if any(i["severity"] in {"ERROR", "CRITICAL"} for i in parcel_issues) else "WARNING" if parcel_issues else "PASS"
        props["review_required"] = bool(parcel_issues) or props.get("review_required") is True

    return {
        "valid_count": sum(1 for _, g, _ in geometries if g.is_valid and not g.is_empty and g.area > 0),
        "invalid_count": sum(1 for _, g, _ in geometries if not g.is_valid or g.is_empty or g.area <= 0),
        "overlap_count": sum(1 for i in issues if i["issue_type"] == "POLYGON_OVERLAP"),
        "noise_count": sum(1 for i in issues if i["issue_type"] == "TINY_NOISE_POLYGON"),
        "issue_count": len(issues),
        "severity_counts": severity_counts,
        "status_counts": status_counts,
        "issues": issues,
    }
