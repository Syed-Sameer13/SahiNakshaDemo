from __future__ import annotations

from typing import Any


SEVERITY_WEIGHTS = {
    "INFO": 2.0,
    "WARNING": 10.0,
    "ERROR": 24.0,
    "CRITICAL": 40.0,
}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def parcel_review_score(
    feature: dict[str, Any],
    validation_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministic review-risk indicator, never an AI correctness probability.

    The score is an ordered triage aid. Every contribution is traceable to
    validation evidence or an actually reported model signal.
    """
    props = feature.get("properties", {})
    issues = validation_issues or []
    parcel_id = str(props.get("parcel_id") or props.get("id") or "unknown")

    score = 0.0
    reasons: list[str] = []
    evidence_factors: list[dict[str, Any]] = []

    def add(points: float, reason: str, source: str, evidence: dict[str, Any] | None = None):
        nonlocal score
        score += points
        reasons.append(reason)
        evidence_factors.append({
            "source": source,
            "points": round(points, 2),
            "reason": reason,
            "evidence": evidence or {},
        })

    # Validation evidence is the strongest and most directly explainable signal.
    for severity in ("CRITICAL", "ERROR", "WARNING", "INFO"):
        count = sum(1 for issue in issues if issue.get("severity") == severity)
        if count:
            points = min(SEVERITY_WEIGHTS[severity] * count, 60.0 if severity in {"CRITICAL", "ERROR"} else 30.0)
            add(points, f"{count} {severity.lower()} validation issue(s)", "validation",
                {"severity": severity, "count": count})

    # Geometry validity is explicitly visible even if a validation issue was filtered.
    if props.get("geometry_valid") is False:
        add(35.0, "Geometry is invalid", "geometry_validity", {"geometry_valid": False})

    # Reference discrepancy.
    discrepancy = str(props.get("discrepancy_status", ""))
    if discrepancy == "MAJOR_DISCREPANCY":
        add(25.0, "Reference discrepancy is major", "reference_comparison",
            {"discrepancy_status": discrepancy})
    elif discrepancy == "MINOR_DISCREPANCY":
        add(12.0, "Reference discrepancy is minor", "reference_comparison",
            {"discrepancy_status": discrepancy})

    # Area discrepancy is a separate, concrete reason.
    area_pct = _number(props.get("percentage_area_difference"))
    if area_pct is not None and area_pct > 5:
        points = min(20.0, area_pct * 1.5)
        add(points, f"Area differs from reference by {area_pct:.1f}%", "area_comparison",
            {"percentage_area_difference": area_pct})

    displacement = _number(props.get("boundary_displacement"))
    if displacement is not None and displacement > 0:
        add(min(15.0, max(3.0, displacement)), "Boundary displacement detected", "reference_comparison",
            {"boundary_displacement": displacement})

    # Boundary evidence is used only when actually measured by the pipeline.
    boundary_evidence = _number(props.get("boundary_evidence"))
    if boundary_evidence is not None and boundary_evidence < 0.6:
        points = min(20.0, max(0.0, (0.6 - boundary_evidence) / 0.6 * 20.0))
        add(points, "AI boundary evidence is weak", "boundary_evidence",
            {"boundary_evidence": boundary_evidence, "threshold": 0.6})

    # Model confidence is optional and only included when a real provider supplied it.
    confidence = _number(props.get("confidence", props.get("model_confidence")))
    if confidence is not None and props.get("confidence_available", True):
        if confidence < 0.65:
            points = min(15.0, max(0.0, (0.65 - confidence) / 0.65 * 15.0))
            add(points, f"Available model confidence is low ({confidence:.2f})", "model_confidence",
                {"model_confidence": confidence})

    if props.get("review_required") is True and not issues:
        add(5.0, "Feature is already marked for human review", "review_required",
            {"review_required": True})

    score = round(min(100.0, score), 1)
    if score >= 70:
        priority = "CRITICAL"
    elif score >= 40:
        priority = "HIGH"
    elif score >= 20:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    if not reasons:
        reasons.append("No deterministic review concern was detected.")

    return {
        "parcel_id": parcel_id,
        "review_score": score,
        "review_priority": priority,
        "review_reasons": reasons,
        "review_evidence": evidence_factors,
        "score_definition": "Deterministic review-risk indicator for surveyor triage; not AI accuracy, confidence, probability, or legal status.",
    }


def enrich_review_scores(feature_collection: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    by_feature: dict[str, list[dict[str, Any]]] = {}
    for issue in validation.get("issues", []):
        by_feature.setdefault(str(issue.get("parcel_id", "unknown")), []).append(issue)

    scores: list[float] = []
    priority_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}

    for feature in feature_collection.get("features", []):
        props = feature.setdefault("properties", {})
        props["geometry_valid"] = bool(props.get("geometry_valid", True))
        result = parcel_review_score(feature, by_feature.get(str(props.get("parcel_id", "unknown")), []))
        props.update(result)
        scores.append(result["review_score"])
        priority_counts[result["review_priority"]] += 1

    feature_collection["review_summary"] = {
        "count": len(scores),
        "mean_review_score": round(sum(scores) / len(scores), 1) if scores else None,
        "priority_counts": priority_counts,
        "high_priority_count": priority_counts["HIGH"] + priority_counts["CRITICAL"],
        "score_definition": "Deterministic review-risk indicator for surveyor triage; not AI accuracy or probability.",
    }
    return feature_collection
