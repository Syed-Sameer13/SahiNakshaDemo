import { useEffect, useMemo, useState } from "react";
import { MapContainer, ImageOverlay, GeoJSON, Marker, Polyline, Polygon, useMapEvents } from "react-leaflet";
import { CRS, divIcon } from "leaflet";
import { supabase } from "../lib/supabase";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const BOUNDS = [[0, 0], [100, 100]];
const STORAGE_PREFIX = "sahinaksha:review:";

function featureType(f) {
  const p = f?.properties || {};
  if (p.building_id != null || p.feature_type === "building") return "building";
  if (p.road_id != null || p.feature_type === "road" || p.feature_type === "road_evidence") return "road";
  return "parcel";
}

function featureId(f) {
  const p = f?.properties || {};
  return `${featureType(f)}:${p.parcel_id || p.building_id || p.road_id || f?.id || "unknown"}`;
}

function readStorage(k, f) {
  try {
    const x = localStorage.getItem(k);
    return x ? JSON.parse(x) : f;
  } catch {
    return f;
  }
}

function clone(x) {
  return JSON.parse(JSON.stringify(x));
}

function polygonArea(g) {
  if (!g) return 0;
  const a = r => Math.abs(r.reduce((s, p, i) => {
    const q = r[(i + 1) % r.length];
    return s + p[0] * q[1] - q[0] * p[1];
  }, 0)) / 2;
  if (g.type === "Polygon") return (g.coordinates || []).reduce((s, r, i) => s + (i ? -a(r) : a(r)), 0);
  return 0;
}

function vertices(g) {
  if (!g || g.type !== "Polygon") return [];
  return (g.coordinates[0] || []).slice(0, -1).map((point, index) => ({ index, point }));
}

function moveVertex(g, index, point) {
  const n = clone(g);
  n.coordinates[0][index] = point;
  if (index === 0) n.coordinates[0][n.coordinates[0].length - 1] = [...point];
  return n;
}

function insertVertex(g, index, point) {
  const n = clone(g);
  n.coordinates[0].splice(index + 1, 0, point);
  return n;
}

function deleteVertex(g, index) {
  const n = clone(g);
  if (n.coordinates[0].length <= 4) return null;
  n.coordinates[0].splice(index, 1);
  if (index === 0) n.coordinates[0][n.coordinates[0].length - 1] = [...n.coordinates[0][0]];
  return n;
}

const vertexIcon = divIcon({ className: "geometry-vertex", html: "<span></span>", iconSize: [14, 14], iconAnchor: [7, 7] });

function EditorVertices({ feature, onChange }) {
  return (
    <>
      {vertices(feature?.geometry).map(v => (
        <Marker
          key={v.index}
          position={[v.point[1], v.point[0]]}
          icon={vertexIcon}
          draggable
          eventHandlers={{
            dragend: e => {
              const p = e.target.getLatLng();
              onChange(moveVertex(feature.geometry, v.index, [p.lng, p.lat]));
            }
          }}
        />
      ))}
    </>
  );
}

function DrawCapture({ active, onPoint }) {
  useMapEvents({
    click: e => {
      if (active) onPoint([e.latlng.lng, e.latlng.lat]);
    }
  });
  return null;
}

const FIELDS = {
  building: ["building_id", "building_use", "floors", "condition", "occupancy", "roof_type", "address", "survey_status", "reviewer_notes"],
  road: ["road_id", "road_type", "surface", "access", "condition", "name", "reviewer_notes"],
  parcel: ["parcel_id", "land_use", "parcel_status", "area", "ownership_ref", "survey_status", "reviewer_notes"]
};

const OPTIONS = {
  building_use: ["Residential", "Commercial", "Industrial", "Institutional", "Mixed Use", "Other"],
  condition: ["Good", "Fair", "Poor", "Unknown"],
  occupancy: ["Occupied", "Vacant", "Under Construction", "Unknown"],
  roof_type: ["Flat", "Pitched", "Metal", "Tile", "Concrete", "Other", "Unknown"],
  survey_status: ["AI Detected", "Human Verified", "Needs Field Survey", "Unknown"],
  road_type: ["Highway", "Main Road", "Street", "Lane", "Path", "Access Road", "Unknown"],
  surface: ["Asphalt", "Concrete", "Gravel", "Dirt", "Paved", "Unknown"],
  access: ["Public", "Private", "Restricted", "Unknown"],
  land_use: ["Residential", "Commercial", "Agricultural", "Industrial", "Institutional", "Vacant", "Mixed Use", "Unknown"],
  parcel_status: ["Preliminary Block", "Reference Parcel", "Human Verified", "Needs Survey"]
};

export default function Dashboard({ result, project, survey, onBack, onReset }) {
  const storageKey = `${STORAGE_PREFIX}${result.analysis_id || "current"}`;
  const original = useMemo(() => ({
    parcels: result.parcels || { type: "FeatureCollection", features: [] },
    buildings: result.buildings || { type: "FeatureCollection", features: [] },
    roads: result.roads || { type: "FeatureCollection", features: [] }
  }), [result]);

  const [layers, setLayers] = useState({ parcels: true, reference: true, buildings: true, roads: true, issues: true });
  const [geometry, setGeometry] = useState(() => readStorage(`${storageKey}:geometry`, {}));
  const [manualFeatures, setManualFeatures] = useState(() => readStorage(`${storageKey}:manual_features`, []));
  const [review, setReview] = useState(() => readStorage(`${storageKey}:decisions`, {}));
  const [edits, setEdits] = useState(() => readStorage(`${storageKey}:edits`, {}));
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(false);
  const [issueFilter, setIssueFilter] = useState("ALL");
  const [saveState, setSaveState] = useState("");
  const [fontScale, setFontScale] = useState(1);
  const [drawMode, setDrawMode] = useState(false);
  const [drawPoints, setDrawPoints] = useState([]);
  const [history, setHistory] = useState([]);
  const [future, setFuture] = useState([]);
  const [message, setMessage] = useState("");
  const [reviewer, setReviewer] = useState(() => localStorage.getItem(`${storageKey}:reviewer`) || "");
  const [reviewComments, setReviewComments] = useState("");
  const [finalMap, setFinalMap] = useState(false);
  const [geometryRevision, setGeometryRevision] = useState(0);

  useEffect(() => {
    try {
      localStorage.setItem(`${storageKey}:geometry`, JSON.stringify(geometry));
      localStorage.setItem(`${storageKey}:manual_features`, JSON.stringify(manualFeatures));
      localStorage.setItem(`${storageKey}:decisions`, JSON.stringify(review));
      localStorage.setItem(`${storageKey}:edits`, JSON.stringify(edits));
      localStorage.setItem(`${storageKey}:reviewer`, reviewer);
    } catch {}
  }, [storageKey, geometry, manualFeatures, review, edits, reviewer]);

  useEffect(() => {
    let active = true;
    (async () => {
      if (!survey?.id) return;
      try {
        const [{ data: parcels, error: parcelError }, { data: reviews, error: reviewError }] = await Promise.all([
          supabase.from("parcels").select("id,parcel_id,status,properties,updated_at").eq("survey_id", survey.id),
          supabase.from("reviews").select("parcel_id,reviewer,decision,comments,previous_status,new_status,created_at").eq("survey_id", survey.id).order("created_at", { ascending: false })
        ]);
        if (parcelError) throw parcelError;
        if (reviewError) throw reviewError;
        if (!active) return;
        const nextReview = {};
        const nextGeometry = {};
        const nextEdits = {};
        (reviews || []).forEach(x => {
          if (nextReview[x.parcel_id] == null) nextReview[x.parcel_id] = x.new_status || x.decision;
        });
        (parcels || []).forEach(row => {
          const props = row.properties || {};
          const id = `parcel:${row.parcel_id}`;
          if (props.review_status) nextReview[id] = props.review_status;
          if (props.edited_geometry) nextGeometry[id] = props.edited_geometry;
          if (Object.keys(props).length) nextEdits[id] = props;
        });
        setReview(x => ({ ...x, ...nextReview }));
        setGeometry(x => ({ ...x, ...nextGeometry }));
        setEdits(x => ({ ...x, ...nextEdits }));
      } catch (e) {
        if (active) setSaveState("Could not load saved review state: " + (e.message || "database error"));
      }
    })();
    return () => { active = false; };
  }, [survey?.id]);

  const all = useMemo(() => [
    ...Object.entries(original).flatMap(([type, c]) => (c.features || []).map(f => ({ ...f, __type: type, geometry: geometry[featureId(f)] || f.geometry }))),
    ...manualFeatures.map(f => ({ ...f, __type: featureType(f), geometry: geometry[featureId(f)] || f.geometry }))
  ], [original, geometry, manualFeatures]);

  const current = selected ? all.find(f => featureId(f) === featureId(selected)) : null;
  const currentId = current ? featureId(current) : "";

  const total = all.length;
  const reviewed = Object.keys(review).length;
  const approved = Object.values(review).filter(v => v === "Approved").length;
  const parcelFeatures = result.parcels?.features || [];
  const validationIssuesList = result.validation?.issues || [];
  const filteredValidationIssues = issueFilter === "ALL" ? validationIssuesList : validationIssuesList.filter(i => i.severity === issueFilter);
  const validationSeverity = result.validation?.severity_counts || {};
  const reviewScores = parcelFeatures.map(f => f.properties?.review_score).filter(v => typeof v === "number");
  const areaSqM = parcelFeatures.map(f => f.properties?.area_sq_m).filter(v => typeof v === "number");
  const meanReview = reviewScores.length ? (reviewScores.reduce((a, b) => a + b, 0) / reviewScores.length).toFixed(1) : "—";
  const totalAreaSqM = areaSqM.length ? areaSqM.reduce((a, b) => a + b, 0).toFixed(2) : "—";
  const validationIssues = result.validation?.issues?.length || 0;

  const select = f => {
    setSelected(f);
    setEditing(false);
    setDrawMode(false);
    setDrawPoints([]);
    setHistory([]);
    setFuture([]);
  };

  const saveReview = async status => {
    if (!current) return;
    setSaveState("Saving review to Supabase…");
    const parcelId = String(current.properties?.parcel_id || currentId.replace(/^parcel:/, ""));
    try {
      if (!survey?.id) throw new Error("Survey ID is missing.");
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Authentication session expired.");
      const { data: existing, error: findError } = await supabase.from("parcels").select("id,status,properties").eq("survey_id", survey.id).eq("parcel_id", parcelId).maybeSingle();
      if (findError) throw findError;
      if (!existing) throw new Error("Persisted parcel record was not found. Re-run processing for this survey.");
      const previousStatus = existing.status || existing.properties?.review_status || "candidate";
      const now = new Date().toISOString();
      const props = {
        ...(existing.properties || {}),
        ...(current.properties || {}),
        ...(edits[currentId] || {}),
        review_status: status,
        reviewer: reviewer || user.email || "authenticated user",
        last_updated: now,
        edited_geometry: geometry[currentId] || current.geometry,
        review_comments: reviewComments
      };
      const payload = {
        status: status.toLowerCase().replaceAll(" ", "_"),
        review_score: props.review_score ?? null,
        review_priority: props.review_priority ?? null,
        properties: props,
        reviewer: user.id,
        reviewed_at: now,
        updated_at: now
      };
      const write = await supabase.from("parcels").update(payload).eq("id", existing.id);
      if (write.error) throw write.error;
      const decision = status === "Approved" ? "ACCEPT" : status === "Rejected" ? "REJECT" : status === "Needs Review" ? "NEEDS_REVIEW" : "REQUEST_FIELD_VERIFICATION";
      const reviewWrite = await supabase.from("reviews").insert({
        survey_id: survey.id,
        parcel_record_id: existing.id,
        parcel_id: parcelId,
        reviewer: user.id,
        decision,
        comments: reviewComments || null,
        previous_status: previousStatus,
        new_status: status,
        edited_geometry: props.edited_geometry || null
      });
      if (reviewWrite.error) throw reviewWrite.error;
      if (props.edited_geometry) {
        const geoWrite = await supabase.rpc("set_parcel_native_geometry", {
          p_parcel_id: existing.id,
          p_geometry: props.edited_geometry,
          p_srid: 0
        });
        if (geoWrite.error) throw geoWrite.error;
      }
      setReview(x => ({ ...x, [currentId]: status }));
      setSaveState("Saved to Supabase ✓");
    } catch (e) {
      setSaveState("Database unavailable: " + (e.message || "unable to save"));
    }
  };

  const requestFieldVerification = () => saveReview("Request Field Verification");

  const applyGeometry = g => {
    if (!currentId) return;
    setHistory(h => [...h, (geometry[currentId] || current.geometry)].slice(-30));
    setFuture([]);
    setGeometry(x => ({ ...x, [currentId]: g }));
    setSelected(x => x ? { ...x, geometry: g } : x);
    setGeometryRevision(v => v + 1);
    setMessage("Boundary updated. Save the review decision to persist in Supabase/PostGIS.");
  };

  const undo = () => {
    if (!history.length) return;
    const prev = history.at(-1);
    setFuture(f => [geometry[currentId] || current.geometry, ...f]);
    setHistory(h => h.slice(0, -1));
    setGeometry(g => ({ ...g, [currentId]: prev }));
    setSelected(s => s ? { ...s, geometry: prev } : s);
  };

  const redo = () => {
    if (!future.length) return;
    const next = future[0];
    setHistory(h => [...h, (geometry[currentId] || current.geometry)].slice(-30));
    setFuture(f => f.slice(1));
    setGeometry(g => ({ ...g, [currentId]: next }));
    setSelected(s => s ? { ...s, geometry: next } : s);
  };

  const addVertex = () => {
    if (!current || current.geometry.type !== "Polygon") return setMessage("Selected feature is not a polygon.");
    const vs = vertices(current.geometry);
    if (!vs.length) return;
    const v = vs[vs.length - 1], n = vs[0];
    const p = [(v.point[0] + n.point[0]) / 2, (v.point[1] + n.point[1]) / 2];
    applyGeometry(insertVertex(current.geometry, v.index, p));
  };

  const deleteVertexAction = () => {
    if (!current) return;
    const vs = vertices(current.geometry);
    if (vs.length <= 3) return setMessage("A polygon must have at least 3 vertices.");
    const g = deleteVertex(current.geometry, vs.length - 1);
    if (g) applyGeometry(g);
  };

  const resetGeometry = () => {
    const source = (original[current?.__type]?.features || []).find(f => featureId(f) === currentId);
    if (source) applyGeometry(source.geometry);
    else {
      const manual = manualFeatures.find(f => featureId(f) === currentId);
      if (manual) applyGeometry(manual.geometry);
    }
  };

  const finalFeatures = all.filter(f => review[featureId(f)] === "Approved").map(f => ({
    ...f,
    geometry: geometry[featureId(f)] || f.geometry,
    properties: {
      ...f.properties,
      ...(edits[featureId(f)] || {}),
      review_status: "Approved",
      reviewed_by: reviewer || "not specified"
    }
  }));

  const exportFinal = async format => {
    if (!API) {
      setMessage("VITE_API_URL is not configured.");
      return;
    }
    setMessage(`Generating authoritative ${format.toUpperCase()} export…`);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) throw new Error("Authentication session expired.");
      const response = await fetch(API.replace(/\/$/, "") + `/api/surveys/${survey.id}/export/${format}`, {
        headers: { Authorization: `Bearer ${session.access_token}` }
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.error?.message || body?.detail || (`Export failed with HTTP ${response.status}`));
      }
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/i);
      const filename = match?.[1] || `sahinaksha-final.${format === "report" ? "pdf" : format}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`Authoritative ${format.toUpperCase()} export ready ✓`);
    } catch (e) {
      setMessage(e.message || "Export failed.");
    }
  };

  const drawPoint = p => setDrawPoints(x => [...x, p]);

  const finishDraw = () => {
    if (drawPoints.length < 3) return setMessage("Place at least 3 points on the aerial imagery.");
    const type = current ? featureType(current) : "parcel";
    const stamp = Date.now();
    const id = `${type}:manual-${stamp}`;
    const f = {
      type: "Feature",
      id: `manual-${stamp}`,
      properties: { feature_type: type, review_status: "Needs Review" },
      geometry: { type: "Polygon", coordinates: [[...drawPoints, drawPoints[0]]] }
    };
    setManualFeatures(x => [...x, f]);
    setReview(r => ({ ...r, [id]: "Needs Review" }));
    setDrawPoints([]);
    setDrawMode(false);
    setSelected(f);
    setMessage("New polygon created and added to survey list ✓");
  };

  const label = k => k.replaceAll("_", " ").replace(/\b\w/g, x => x.toUpperCase());
  const jump = id => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <main className="dashboard gov-portal" style={{ fontSize: `${fontScale}em` }}>
      {/* Government Top Strip */}
      <div className="gov-top-strip">
        <div>भारत सरकार &nbsp;|&nbsp; Government of India</div>
        <div className="gov-tools">
          <button type="button" onClick={() => jump("dashboard-workspace")}>Skip to Map</button>
          <button type="button" onClick={() => setFontScale(v => Math.max(0.9, v - 0.05))}>A−</button>
          <button type="button" onClick={() => setFontScale(1)}>A</button>
          <button type="button" onClick={() => setFontScale(v => Math.min(1.15, v + 0.05))}>A+</button>
        </div>
      </div>

      {/* Government Header */}
      <header className="gov-header dashboard-header">
        <div className="gov-brand">
          <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Government_of_India_logo.svg/120px-Government_of_India_logo.svg.png" alt="Government of India emblem" />
          <div>
            <div className="gov-hindi">ग्रामीण विकास मंत्रालय</div>
            <div className="gov-title">MINISTRY OF RURAL DEVELOPMENT</div>
            <div className="gov-subtitle">GOVERNMENT OF INDIA</div>
          </div>
        </div>
        <div className="header-identity">
          <img className="ministry-logo" src="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Ministry_of_Rural_Development.png/250px-Ministry_of_Rural_Development.png" alt="Ministry of Rural Development logo" />
          <div className="sahinaksha-brand">
            <strong>Sahi<span>Naksha</span></strong>
            <span>AI-Assisted Cadastral Mapping</span>
          </div>
        </div>
      </header>

      {/* Nav */}
      <nav className="gov-nav">
        <button type="button" className="active" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>🗺️ GIS Dashboard</button>
        <button type="button" onClick={() => jump("dashboard-workspace")}>📐 Land &amp; Survey Editor</button>
        <button type="button" onClick={() => jump("dashboard-report")}>📊 Metrics &amp; Validation</button>
      </nav>

      <div className="gov-notice">
        <b>Prototype Portal</b> — SIH 2026 demonstration system; not an official Government of India service.
      </div>

      {/* Action Toolbar */}
      <header className="topbar">
        <div>
          <div className="brand">Sahi<span>Naksha</span> WebGIS Workspace</div>
          <small>{project?.name || "Project"} &nbsp;•&nbsp; {survey?.name || "Survey"}</small>
        </div>
        <div className="actions">
          <button className={finalMap ? "primary-button" : "secondary-button"} onClick={() => setFinalMap(v => !v)}>
            {finalMap ? "🔍 Show AI Raw Map" : "✅ Show Final Approved Map"}
          </button>
          <button className="secondary-button" onClick={() => exportFinal("geojson")} disabled={!approved}>
            📥 GeoJSON
          </button>
          <button className="secondary-button" onClick={() => exportFinal("csv")} disabled={!approved}>
            📊 CSV
          </button>
          <button className="secondary-button" onClick={() => exportFinal("report")} disabled={!approved}>
            📄 PDF Report
          </button>
          <button className="secondary-button" onClick={onBack}>
            ← Back to Upload
          </button>
          <button className="secondary-button" onClick={onReset}>
            📁 Projects
          </button>
        </div>
      </header>

      {/* AI Engine Status Banner */}
      <section className="ai-status-panel">
        <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <span className="badge">AI Pipeline Engine</span>
            <div style={{ marginTop: "4px", fontSize: "13px", fontWeight: 700, color: "var(--gov-navy)" }}>
              Status: {result.ai_engine?.status || result.processing_status || "UNKNOWN"} &nbsp;•&nbsp; Model: {result.ai_engine?.model_name || result.ai_engine?.model_provider || "Standard"}
            </div>
          </div>
          <div>
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              {result.ai_engine?.fallback_used
                ? "⚠️ Learned model unavailable; deterministic image fallback was used."
                : result.ai_engine?.status === "COMPLETED"
                  ? "✓ Learned AI segmentation completed."
                  : "⚠️ AI status requires verification."}
            </span>
          </div>
        </div>
      </section>

      {/* Summary Grid */}
      <section className="summary-grid">
        <div>
          <b>{original.parcels.features.length + manualFeatures.filter(f => featureType(f) === "parcel").length}</b>
          <span>Parcel Blocks</span>
        </div>
        <div>
          <b>{original.buildings.features.length + manualFeatures.filter(f => featureType(f) === "building").length}</b>
          <span>Buildings Extracted</span>
        </div>
        <div>
          <b>{original.roads.features.length + manualFeatures.filter(f => featureType(f) === "road").length}</b>
          <span>Road Features</span>
        </div>
        <div>
          <b style={{ color: "var(--primary-text)" }}>{reviewed} / {total}</b>
          <span>Reviewed Parcels</span>
        </div>
      </section>

      {/* Metrics Cards */}
      <section id="dashboard-report" className="report-grid">
        <div className="report-card">
          <b>{meanReview}</b>
          <span>Mean Review-Risk Indicator</span>
          <small>Deterministic GIS triage aid (0 = verified, 100 = high risk).</small>
        </div>
        <div className="report-card">
          <b>{totalAreaSqM === "—" ? "Local Units" : totalAreaSqM + " m²"}</b>
          <span>Total Cadastral Area</span>
          <small>{areaSqM.length ? "Computed from metric projected CRS" : "Raster local coordinate frame."}</small>
        </div>
        <div className="report-card">
          <b style={{ color: validationIssues > 0 ? "var(--gov-saffron)" : "var(--gov-green)" }}>{validationIssues}</b>
          <span>Topology &amp; Boundary Issues</span>
          <small>Surveyor review needed before final land record export.</small>
        </div>
        <div className="report-card">
          <b>{result.topology_stats?.overlap_conflicts_resolved || 0}</b>
          <span>Auto-Cleaned Overlaps</span>
          <small>Deterministic topology sanitization pass.</small>
        </div>
      </section>

      {/* Validation Panel */}
      <section className="validation-panel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
          <div>
            <h3 style={{ fontSize: "15px", fontWeight: 800, color: "var(--gov-navy)" }}>🛡️ Explainable Validation &amp; Boundary Triage</h3>
            <p style={{ margin: "2px 0 0", color: "var(--text-secondary)", fontSize: "12px" }}>
              Automated checks identify geometry errors, reference discrepancies, and overlapping polygons.
            </p>
          </div>
          <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-muted)" }}>Filter:</span>
            {["ALL", "INFO", "WARNING", "ERROR", "CRITICAL"].map(level => (
              <button
                key={level}
                type="button"
                className={issueFilter === level ? "primary-button compact" : "secondary-button compact"}
                onClick={() => setIssueFilter(level)}
              >
                {level} {level === "ALL" ? validationIssuesList.length : (validationSeverity[level] || 0)}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "10px", marginTop: "14px" }}>
          <div className="badge" style={{ justifyContent: "center" }}>
            ✓ Geometry Valid: {result.validation?.invalid_count ? `${result.validation.invalid_count} Invalid` : "PASS"}
          </div>
          <div className="badge" style={{ justifyContent: "center", background: validationSeverity.WARNING ? "var(--warning-bg)" : "var(--bg-subtle)", color: validationSeverity.WARNING ? "var(--warning-text)" : "var(--text-muted)", borderColor: validationSeverity.WARNING ? "var(--warning-border)" : "var(--border-subtle)" }}>
            {validationSeverity.WARNING ? "⚠" : "✓"} Warnings: {validationSeverity.WARNING || 0}
          </div>
          <div className="badge" style={{ justifyContent: "center", background: validationSeverity.ERROR ? "var(--danger-bg)" : "var(--bg-subtle)", color: validationSeverity.ERROR ? "var(--danger-text)" : "var(--text-muted)", borderColor: validationSeverity.ERROR ? "var(--danger-border)" : "var(--border-subtle)" }}>
            {validationSeverity.ERROR ? "⚠" : "✓"} Errors: {validationSeverity.ERROR || 0}
          </div>
          <div className="badge" style={{ justifyContent: "center", background: validationSeverity.CRITICAL ? "var(--danger-bg)" : "var(--bg-subtle)", color: validationSeverity.CRITICAL ? "var(--danger-text)" : "var(--text-muted)", borderColor: validationSeverity.CRITICAL ? "var(--danger-border)" : "var(--border-subtle)" }}>
            {validationSeverity.CRITICAL ? "⚠" : "✓"} Critical: {validationSeverity.CRITICAL || 0}
          </div>
        </div>

        <div style={{ marginTop: "14px" }}>
          {filteredValidationIssues.length === 0 ? (
            <div className="success" style={{ textAlign: "center" }}>✓ No validation issues found in this category.</div>
          ) : (
            <div style={{ display: "grid", gap: "8px", maxHeight: "240px", overflowY: "auto" }}>
              {filteredValidationIssues.map(issue => (
                <div key={issue.issue_id} style={{ padding: "10px 14px", border: "1px solid var(--border-subtle)", borderLeft: "4px solid var(--gov-saffron)", borderRadius: "var(--radius-md)", background: "var(--bg-main)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", flexWrap: "wrap", fontSize: "12px" }}>
                    <strong>{issue.parcel_id} &nbsp;•&nbsp; {issue.issue_type}</strong>
                    <span className="badge" style={{ background: issue.severity === "CRITICAL" || issue.severity === "ERROR" ? "var(--danger-bg)" : "var(--warning-bg)", color: issue.severity === "CRITICAL" || issue.severity === "ERROR" ? "var(--danger-text)" : "var(--warning-text)", borderColor: "transparent" }}>
                      {issue.severity}
                    </span>
                  </div>
                  <div style={{ marginTop: "4px", fontSize: "12px", color: "var(--text-primary)" }}>{issue.description}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Editor Banner Toolbar */}
      <section className="editor-banner">
        <div>
          <b>📐 Interactive Boundary Editor</b>
          <span style={{ display: "block", marginTop: "2px" }}>Click features on the map to inspect, edit vertices, draw new parcels, or record surveyor review decisions.</span>
        </div>
        <div className="editor-tools">
          <button className={editing ? "primary-button" : "secondary-button"} disabled={!current || finalMap} onClick={() => setEditing(v => !v)}>
            {editing ? "✓ Done Editing" : "✏️ Edit Boundary"}
          </button>
          <button className="secondary-button" disabled={!editing} onClick={addVertex}>
            ➕ Add Vertex
          </button>
          <button className="secondary-button" disabled={!editing} onClick={deleteVertexAction}>
            ➖ Delete Vertex
          </button>
          <button className="secondary-button" disabled={!editing || !history.length} onClick={undo}>
            ↩️ Undo
          </button>
          <button className="secondary-button" disabled={!editing || !future.length} onClick={redo}>
            ↪️ Redo
          </button>
          <button className="secondary-button" disabled={!editing} onClick={resetGeometry}>
            🔄 Reset AI
          </button>
          <button className={drawMode ? "primary-button" : "secondary-button"} disabled={finalMap} onClick={() => { setDrawMode(v => !v); setDrawPoints([]); }}>
            {drawMode ? "✕ Cancel Draw" : "➕ Draw Polygon"}
          </button>
          {drawMode && (
            <button className="primary-button" onClick={finishDraw}>
              ✓ Finish Polygon
            </button>
          )}
        </div>
        {message && <div className="success" style={{ width: "100%", margin: "8px 0 0" }}>{message}</div>}
      </section>

      {/* Workspace: Sidebar + Map */}
      <section id="dashboard-workspace" className="workspace">
        {/* Left Sidebar */}
        <aside className="sidebar">
          <h3>GIS Layers</h3>
          <div style={{ display: "grid", gap: "4px" }}>
            {Object.keys(layers).map(k => (
              <label className="toggle" key={k}>
                <input type="checkbox" checked={layers[k]} onChange={() => setLayers(x => ({ ...x, [k]: !x[k] }))} />
                <span>{k} Layer</span>
              </label>
            ))}
          </div>

          <hr />

          <h3>Feature Review</h3>
          {current ? (
            <>
              <div className="selected-title">
                <span className="feature-type-badge">{featureType(current)}</span>
                <strong style={{ fontSize: "12px", color: "var(--gov-navy)", overflow: "hidden", textOverflow: "ellipsis" }}>{currentId}</strong>
              </div>

              <div className="details">
                {FIELDS[featureType(current)].map(k => (
                  <label className="edit-field" key={k}>
                    <span>{label(k)}</span>
                    {OPTIONS[k] ? (
                      <select
                        value={edits[currentId]?.[k] ?? current.properties?.[k] ?? ""}
                        onChange={e => setEdits(x => ({ ...x, [currentId]: { ...(x[currentId] || {}), [k]: e.target.value } }))}
                      >
                        <option value="">Select...</option>
                        {OPTIONS[k].map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input
                        value={edits[currentId]?.[k] ?? current.properties?.[k] ?? ""}
                        onChange={e => setEdits(x => ({ ...x, [currentId]: { ...(x[currentId] || {}), [k]: e.target.value } }))}
                      />
                    )}
                  </label>
                ))}
              </div>

              <label className="reviewer-field">
                <span>Reviewer Name</span>
                <input value={reviewer} onChange={e => setReviewer(e.target.value)} placeholder="Surveyor name or Officer ID" />
              </label>

              <label className="reviewer-field">
                <span>Surveyor Review Notes</span>
                <textarea value={reviewComments} onChange={e => setReviewComments(e.target.value)} placeholder="Reason for review decision / survey notes" />
              </label>

              <div className="review-buttons">
                <button type="button" onClick={() => saveReview("Approved")}>✓ Accept</button>
                <button type="button" onClick={() => saveReview("Needs Review")}>⚠ Needs Review</button>
                <button type="button" onClick={() => saveReview("Rejected")}>✕ Reject</button>
                <button type="button" onClick={requestFieldVerification}>📍 Request Field Verification</button>
              </div>

              {saveState && <div className="review-status">{saveState}</div>}
              {review[currentId] && <div className="review-status">{review[currentId]} &nbsp;•&nbsp; Saved in Supabase</div>}

              <div className="geometry-help">
                <b>Feature Metrics &amp; Provenance</b>
                <span>Area: {current.properties?.area_sq_m != null ? `${current.properties.area_sq_m} m²` : `${polygonArea(current.geometry).toFixed(2)} image units²`}</span>
                <span>Perimeter: {current.properties?.perimeter_m ?? current.properties?.parcel_perimeter ?? "—"}{current.properties?.perimeter_m != null ? " m" : ""}</span>
                <span>CRS: {result.raster_metadata?.crs || "Local pixel frame"}</span>
                <span>AI Evidence: {current.properties?.ai_evidence || current.properties?.boundary_evidence || "Physical boundary evidence detected"}</span>
                <span>Ref Area: {current.properties?.reference_area ?? "—"}</span>
                <span>Area Difference: {current.properties?.percentage_area_difference != null ? `${current.properties.percentage_area_difference.toFixed?.(1) || current.properties.percentage_area_difference}%` : "—"}</span>
              </div>
            </>
          ) : (
            <p className="muted" style={{ padding: "16px 0", textAlign: "center" }}>Click any parcel, building or road on the map to inspect and edit.</p>
          )}

          <hr />
          <p className="muted" style={{ fontSize: "11px" }}>All parcel boundaries, attributes, and surveyor decisions persist in Supabase / PostGIS.</p>
        </aside>

        {/* Right Map Canvas */}
        <div className="map-wrap">
          <MapContainer crs={CRS.Simple} bounds={BOUNDS} minZoom={-2} maxZoom={5} zoom={0} style={{ height: "100%", width: "100%" }}>
            <DrawCapture active={drawMode} onPoint={drawPoint} />
            {result.original_image_url && (
              <ImageOverlay url={result.original_image_url} bounds={BOUNDS} opacity={0.92} />
            )}
            {!finalMap && layers.reference && result.reference_parcels && (
              <GeoJSON data={result.reference_parcels} style={{ color: "#7c3aed", weight: 2, dashArray: "6 5", fillOpacity: 0.03 }} />
            )}
            {!finalMap && layers.parcels && (
              <GeoJSON
                key={`parcels-${geometryRevision}`}
                data={{ type: "FeatureCollection", features: all.filter(f => featureType(f) === "parcel") }}
                style={(f) => ({
                  color: featureId(f) === currentId ? "#dc2626" : "#0d9488",
                  weight: featureId(f) === currentId ? 3.5 : 2.5,
                  fillOpacity: featureId(f) === currentId ? 0.18 : 0.1
                })}
                onEachFeature={(f, l) => l.on({ click: () => select(f) })}
              />
            )}
            {!finalMap && layers.buildings && (
              <GeoJSON
                key={`buildings-${geometryRevision}`}
                data={{ type: "FeatureCollection", features: all.filter(f => featureType(f) === "building") }}
                style={{ color: "#0284c7", weight: 2, fillOpacity: 0.12 }}
                onEachFeature={(f, l) => l.on({ click: () => select(f) })}
              />
            )}
            {!finalMap && layers.roads && (
              <GeoJSON
                data={{ type: "FeatureCollection", features: all.filter(f => featureType(f) === "road") }}
                style={{ color: "#d97706", weight: 3, fillOpacity: 0.08 }}
                onEachFeature={(f, l) => l.on({ click: () => select(f) })}
              />
            )}
            {finalMap && (
              <GeoJSON
                data={{ type: "FeatureCollection", features: finalFeatures }}
                style={{ color: "#16a34a", weight: 3, fillOpacity: 0.15 }}
              />
            )}
            {editing && current && current.geometry?.type === "Polygon" && (
              <>
                <Polygon
                  positions={(geometry[currentId] || current.geometry).coordinates[0].map(p => [p[1], p[0]])}
                  pathOptions={{ color: "#dc2626", weight: 4, fillOpacity: 0.18 }}
                />
                <EditorVertices
                  feature={{ ...current, geometry: geometry[currentId] || current.geometry }}
                  onChange={applyGeometry}
                />
              </>
            )}
            {drawMode && drawPoints.length > 1 && (
              <Polyline positions={drawPoints.map(p => [p[1], p[0]])} weight={2} dashArray="5 5" color="#0d9488" />
            )}
            {drawMode && drawPoints.length >= 3 && (
              <Polygon positions={drawPoints.map(p => [p[1], p[0]])} fillOpacity={0.1} weight={1} color="#0d9488" />
            )}
          </MapContainer>
          <div className="map-note">
            {layers.reference && result.reference_parcels ? "🟣 Purple dashed: Reference GIS. " : ""}
            {drawMode ? "✏️ Click points on the aerial map, then Finish." : editing ? "🖐️ Drag white circle vertices directly on the map." : finalMap ? "✅ Final Verified Map: Approved parcels only." : "👆 Click any polygon to select and review."}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer id="dashboard-help" className="gov-footer">
        <div><b>Government of India</b><br />Ministry of Rural Development • SahiNaksha Demonstration Portal</div>
        <div>Privacy Policy &nbsp;|&nbsp; Terms of Service &nbsp;|&nbsp; Accessibility &nbsp;|&nbsp; Help &amp; Support</div>
      </footer>
    </main>
  );
}
