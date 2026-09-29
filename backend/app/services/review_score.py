from __future__ import annotations

from typing import Any


def parcel_review_score(feature: dict[str, Any], validation_issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Deterministic review-priority score; it is NOT model accuracy or probability."""
    props = feature.get("properties", {})
    issues = validation_issues or []
    parcel_id = str(props.get("parcel_id") or props.get("id") or "unknown")

    score = 100.0
    reasons: list[str] = []

    if props.get("geometry_valid") is False:
        score -= 40
        reasons.append("invalid geometry")

    issue_count = len(issues)
    score -= min(30, issue_count * 10)
    if issue_count:
        reasons.append(f"{issue_count} validation issue(s)")

    evidence = props.get("boundary_evidence")
    if isinstance(evidence, (int, float)):
        score -= max(0, 20 * (1 - float(evidence)))
        if float(evidence) < 0.6:
            reasons.append("weak boundary image evidence")

    confidence = props.get("confidence", props.get("model_confidence"))
    if isinstance(confidence, (int, float)):
        score -= max(0, 15 * (1 - float(confidence)))
        if float(confidence) < 0.65:
            reasons.append("low model confidence")

    if props.get("review_required") is True:
        reasons.append("marked for human review")

    score = max(0.0, min(100.0, score))
    if score >= 85:
        priority = "low"
    elif score >= 65:
        priority = "medium"
    else:
        priority = "high"

    return {
        "parcel_id": parcel_id,
        "review_score": round(score, 1),
        "review_priority": priority,
        "review_reasons": reasons,
        "score_definition": "Human-review priority from deterministic GIS/evidence signals; not AI accuracy.",
    }


def enrich_review_scores(feature_collection: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    by_feature: dict[str, list[dict[str, Any]]] = {}
    for issue in validation.get("issues", []):
        feature_id = str(issue.get("feature_id", "unknown"))
        for token in feature_id.split(" / "):
            by_feature.setdefault(token, []).append(issue)

    scores = []
    for feature in feature_collection.get("features", []):
        props = feature.setdefault("properties", {})
        props["geometry_valid"] = bool(props.get("geometry_valid", True))
        result = parcel_review_score(feature, by_feature.get(str(props.get("parcel_id", "unknown")), []))
        props.update(result)
        scores.append(result["review_score"])

    feature_collection["review_summary"] = {
        "count": len(scores),
        "mean_review_score": round(sum(scores) / len(scores), 1) if scores else None,
        "high_priority_count": sum(1 for f in feature_collection.get("features", []) if f.get("properties", {}).get("review_priority") == "high"),
    }
    return feature_collection
