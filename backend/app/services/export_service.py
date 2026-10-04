import json
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


LIMITATION = (
    "AI-generated boundaries are preliminary and require surveyor verification. "
    "They must not be interpreted as legally authoritative cadastral boundaries."
)


def serialize_geojson(state):
    features = []
    for row in state.get("parcels", []):
        props = {
            "parcel_id": row.get("parcel_id"),
            "area_sq_m": row.get("area_sq_m"),
            "perimeter_m": row.get("perimeter_m"),
            "review_priority": row.get("review_priority"),
            "review_status": row.get("review_status"),
            "validation_issue_count": row.get("validation_issue_count", 0),
            "validation_summary": row.get("validation_summary", {}),
            "reference_area": row.get("reference_area"),
            "area_difference_percent": row.get("area_difference_percent"),
            "reviewer": row.get("reviewer"),
            "provenance": row.get("provenance", {}),
        }
        features.append({
            "type": "Feature",
            "id": row.get("parcel_record_id"),
            "geometry": row.get("geometry"),
            "properties": props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "project": state.get("project", {}),
            "survey": state.get("survey", {}),
            "processing": state.get("processing", {}),
            "provenance": state.get("provenance", {}),
            "validation_summary": state.get("validation_summary", {}),
            "legal_status": "preliminary_output_requires_authoritative_cadastral_and_survey_validation",
            "limitations": [LIMITATION],
        },
    }


def to_json_bytes(result):
    return json.dumps(result, indent=2, default=str).encode("utf-8")


def build_pdf_report(state):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="SahiNaksha Preliminary Cadastral Survey Report",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], spaceBefore=8, spaceAfter=6))
    story = [
        Paragraph("<b>SahiNaksha</b>", styles["Title"]),
        Paragraph("Preliminary Cadastral Survey Report", styles["Heading2"]),
        Spacer(1, 6),
    ]

    project = state.get("project", {})
    survey = state.get("survey", {})
    processing = state.get("processing", {})
    rows = [
        ["Project", project.get("name", "—")],
        ["Project description", project.get("description") or "—"],
        ["Survey", survey.get("name", "—")],
        ["Processing date", processing.get("completed_at") or processing.get("started_at") or "—"],
        ["Input imagery", survey.get("source_image_url") or processing.get("input", {}).get("orthomosaic") or "—"],
        ["CRS", survey.get("source_crs") or "Not georeferenced"],
        ["Model used", processing.get("model_used") or "Not reported"],
    ]
    t = Table(rows, colWidths=[42 * mm, 135 * mm])
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [Paragraph("Project & Survey Information", styles["Section"]), t]

    summary = state.get("summary", {})
    summary_rows = [
        ["Total candidate parcels", summary.get("total_candidate_parcels", 0)],
        ["Reviewed parcels", summary.get("reviewed_parcels", 0)],
        ["Accepted parcels", summary.get("accepted_parcels", 0)],
        ["Rejected parcels", summary.get("rejected_parcels", 0)],
        ["Field verification requests", summary.get("field_verification_requests", 0)],
        ["Total area (m²)", summary.get("total_area_sq_m", "Not available")],
    ]
    t = Table(summary_rows, colWidths=[90 * mm, 87 * mm])
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),("BACKGROUND",(0,0),(0,-1),colors.whitesmoke)]))
    story += [Paragraph("Summary", styles["Section"]), t]

    validation = state.get("validation_summary", {})
    vt = Table([
        ["Errors", validation.get("errors", 0)],
        ["Warnings", validation.get("warnings", 0)],
        ["Discrepancies", validation.get("discrepancies", 0)],
    ], colWidths=[90 * mm, 87 * mm])
    vt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),("BACKGROUND",(0,0),(0,-1),colors.whitesmoke)]))
    story += [Paragraph("Validation Summary", styles["Section"]), vt, Spacer(1, 5)]

    story.append(Paragraph("Parcel Table", styles["Section"]))
    data = [["Parcel ID", "Area", "Priority", "Review Status", "Issues"]]
    for row in state.get("parcels", []):
        data.append([
            str(row.get("parcel_id") or "—"),
            str(row.get("area_sq_m") if row.get("area_sq_m") is not None else "—"),
            str(row.get("review_priority") or "—"),
            str(row.get("review_status") or "—"),
            str(row.get("validation_issue_count", 0)),
        ])
    pt = Table(data, colWidths=[35*mm, 30*mm, 30*mm, 48*mm, 22*mm], repeatRows=1)
    pt.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.35,colors.grey),
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e9eef3")),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    story += [pt, Spacer(1, 8), Paragraph("<b>Limitations</b>", styles["Section"]), Paragraph(LIMITATION, styles["BodyText"])]
    doc.build(story)
    return buffer.getvalue()
