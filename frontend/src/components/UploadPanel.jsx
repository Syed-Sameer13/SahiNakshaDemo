import { useState } from "react";
import { supabase } from "../lib/supabase";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function UploadPanel({ project, survey, onComplete, onBack }) {
  const [file, setFile] = useState(null);
  const [reference, setReference] = useState(null);
  const [groundTruth, setGroundTruth] = useState(null);
  const [dsm, setDsm] = useState(null);
  const [preview, setPreview] = useState(null);
  const [stage, setStage] = useState("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  const choose = (f, setter, accept, label) => {
    if (!f) return;
    if (!accept(f)) {
      setError(label);
      return;
    }
    setError("");
    setter(f);
    if (f.type.startsWith("image/")) setPreview(URL.createObjectURL(f));
  };

  async function updateSurvey(status, extra = {}) {
    if (!survey?.id) return;
    try {
      await supabase.from("surveys").update({ status, ...extra }).eq("id", survey.id);
    } catch {}
  }

  async function analyze() {
    if (!file) {
      setError("Please select the required orthomosaic / drone image.");
      return;
    }
    if (!survey?.id) {
      setError("No active survey workspace selected. Please select or create a survey in the Project Dashboard.");
      return;
    }
    setError("");
    setProgress(5);
    setStage("Uploading inputs");
    await updateSurvey("uploading");
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) throw new Error("Authentication session expired. Please sign in again.");
      const headers = { Authorization: `Bearer ${session.access_token}` };
      const base = API.replace(/\/$/, "");
      const body = new FormData();
      body.append("file", file);
      if (reference) body.append("reference_parcels", reference);
      if (groundTruth) body.append("ground_truth", groundTruth);
      if (dsm) body.append("dsm", dsm);

      const uploadResponse = await fetch(base + `/api/surveys/${survey.id}/upload`, { method: "POST", body, headers });
      const uploadType = uploadResponse.headers.get("content-type") || "";
      const uploadData = uploadType.includes("application/json") ? await uploadResponse.json() : { error: { message: await uploadResponse.text() } };
      if (!uploadResponse.ok) throw new Error(uploadData?.error?.message || uploadData?.detail || ("Upload failed with HTTP " + uploadResponse.status));

      setProgress(20);
      setStage("Queued in processing engine");
      await updateSurvey("processing");
      const processResponse = await fetch(base + `/api/surveys/${survey.id}/process`, { method: "POST", headers });
      const processData = await processResponse.json().catch(() => ({}));
      if (!processResponse.ok) throw new Error(processData?.error?.message || processData?.detail || ("Processing request failed with HTTP " + processResponse.status));

      let statusData = processData;
      for (let attempt = 0; attempt < 120; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const statusResponse = await fetch(base + `/api/surveys/${survey.id}/processing-status`, { headers });
        statusData = await statusResponse.json().catch(() => ({}));
        if (!statusResponse.ok) throw new Error(statusData?.error?.message || statusData?.detail || ("Status request failed with HTTP " + statusResponse.status));
        const s = String(statusData.status || "").toUpperCase();
        setStage(statusData.stage || s || "AI Segmentation & Cadastral Mapping");
        setProgress(typeof statusData.progress === "number" ? statusData.progress : Math.min(95, 25 + attempt));
        if (s === "COMPLETED") break;
        if (s === "FAILED") throw new Error(statusData.error || "AI/GIS processing failed.");
        if (attempt === 119) throw new Error("Processing timed out while waiting for the backend job.");
      }

      setProgress(96);
      setStage("Finalizing vector topology & metrics");
      const resultResponse = await fetch(base + `/api/surveys/${survey.id}/results`, { headers });
      const resultData = await resultResponse.json().catch(() => ({}));
      if (!resultResponse.ok) throw new Error(resultData?.error?.message || resultData?.detail || ("Results request failed with HTTP " + resultResponse.status));
      const payload = resultData.result || resultData;
      await updateSurvey("complete", {
        source_crs: payload.raster_metadata?.crs || null,
        source_image_url: payload.original_image_url || uploadData.source_image_url || null
      });
      setProgress(100);
      setStage("Complete");
      onComplete({
        ...payload,
        original_image_url: (payload.original_image_url || uploadData.source_image_url || "").startsWith("http")
          ? (payload.original_image_url || uploadData.source_image_url)
          : base + (payload.original_image_url || uploadData.source_image_url),
        project_id: project?.id,
        survey_id: survey?.id,
        project_name: project?.name,
        survey_name: survey?.name
      });
    } catch (e) {
      console.error("Upload & Analysis Error:", e);
      let msg = e.message || "Processing failed.";
      if (e instanceof TypeError && e.message.includes("fetch")) {
        msg = `Backend connection error (${e.message}). Ensure FastAPI is running on ${API}.`;
      }
      setError(msg);
      await updateSurvey("failed");
      setStage("");
    }
  }

  return (
    <main className="gov-portal">
      <div className="gov-top-strip">
        <div>भारत सरकार &nbsp;|&nbsp; Government of India</div>
        <div className="gov-tools">
          <button type="button" onClick={onBack}>← Back to Projects</button>
        </div>
      </div>
      <header className="gov-header">
        <div className="gov-brand">
          <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Government_of_India_logo.svg/120px-Government_of_India_logo.svg.png" alt="Government of India emblem" />
          <div>
            <div className="gov-hindi">ग्रामीण विकास मंत्रालय</div>
            <div className="gov-title">MINISTRY OF RURAL DEVELOPMENT</div>
            <div className="gov-subtitle">GOVERNMENT OF INDIA</div>
          </div>
        </div>
        <div className="sahinaksha-brand">
          <strong>Sahi<span>Naksha</span></strong>
          <span>AI-Assisted Cadastral Mapping</span>
        </div>
      </header>
      <div className="gov-notice">
        <b>Prototype Portal</b> — SIH 2026 demonstration system; not an official Government of India service.
      </div>
      <section className="gov-content">
        <div className="gov-page-title">
          <span>03 • DATA INGESTION &amp; PIPELINE EXECUTION</span>
          <small>{project?.name} &nbsp;•&nbsp; {survey?.name}</small>
        </div>
        <div className="workflow-heading">
          <span>Survey Ingestion</span>
          <h2>Upload &amp; Validate Inputs</h2>
          <p>Provide high-resolution aerial orthomosaic imagery and optional reference GIS layers for automated AI feature extraction.</p>
        </div>

        <div className="upload-card">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px", marginBottom: "16px" }}>
            {/* Required Orthomosaic */}
            <label className="file-picker">
              <span>Required: Orthomosaic / Drone Raster <b style={{ color: "var(--danger-text)" }}>*</b></span>
              <input type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" onChange={e => choose(e.target.files?.[0], setFile, f => ["image/jpeg", "image/png"].includes(f.type), "Only JPG/PNG imagery is supported.")} />
              <div className="file-picker-btn" style={{ borderColor: file ? "var(--primary)" : "var(--border-medium)", background: file ? "var(--primary-light)" : "var(--bg-subtle)" }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file ? `✓ ${file.name}` : "📁 Select Aerial Image"}</span>
                <span className="badge" style={{ fontSize: "10px" }}>{file ? "Ready" : "Required"}</span>
              </div>
            </label>

            {/* Reference Parcels */}
            <label className="file-picker">
              <span>Optional: Reference Parcel GIS (GeoJSON)</span>
              <input type="file" accept=".json,.geojson" onChange={e => choose(e.target.files?.[0], setReference, f => /\.(json|geojson)$/i.test(f.name), "Reference parcels must be GeoJSON format.")} />
              <div className="file-picker-btn" style={{ borderColor: reference ? "var(--primary)" : "var(--border-medium)", background: reference ? "var(--primary-light)" : "var(--bg-subtle)" }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{reference ? `✓ ${reference.name}` : "🗺️ Select Reference GeoJSON"}</span>
                <span className="badge" style={{ fontSize: "10px" }}>{reference ? "Loaded" : "Optional"}</span>
              </div>
            </label>

            {/* DSM / DTM */}
            <label className="file-picker">
              <span>Optional: Digital Surface Model (DSM)</span>
              <input type="file" accept=".jpg,.jpeg,.png" onChange={e => choose(e.target.files?.[0], setDsm, f => /\.(jpg|jpeg|png)$/i.test(f.name), "DSM input must be aligned JPG/PNG format.")} />
              <div className="file-picker-btn" style={{ borderColor: dsm ? "var(--primary)" : "var(--border-medium)", background: dsm ? "var(--primary-light)" : "var(--bg-subtle)" }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{dsm ? `✓ ${dsm.name}` : "🏔️ Select Height Raster"}</span>
                <span className="badge" style={{ fontSize: "10px" }}>{dsm ? "Loaded" : "Optional"}</span>
              </div>
            </label>

            {/* Ground Truth */}
            <label className="file-picker">
              <span>Optional: Ground Truth Benchmark</span>
              <input type="file" accept=".json,.geojson" onChange={e => choose(e.target.files?.[0], setGroundTruth, f => /\.(json|geojson)$/i.test(f.name), "Ground truth must be GeoJSON format.")} />
              <div className="file-picker-btn" style={{ borderColor: groundTruth ? "var(--primary)" : "var(--border-medium)", background: groundTruth ? "var(--primary-light)" : "var(--bg-subtle)" }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{groundTruth ? `✓ ${groundTruth.name}` : "🎯 Select Ground Truth"}</span>
                <span className="badge" style={{ fontSize: "10px" }}>{groundTruth ? "Loaded" : "Optional"}</span>
              </div>
            </label>
          </div>

          {preview && (
            <div style={{ textAlign: "center", margin: "16px 0" }}>
              <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>Preview Image</span>
              <img className="preview" src={preview} alt="Orthomosaic preview" />
            </div>
          )}

          {stage && (
            <div className="upload-progress">
              <b>
                <span>⚙️ {stage}</span>
                <span>{progress}%</span>
              </b>
              <div className="progress-bar-bg">
                <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {error && <p className="error">{error}</p>}

          <div className="gov-form-note">
            <b>🛡️ Strict Quality Gate:</b> Real physical feature evidence is segmented using our trained pixel/ONNX models. Reference parcels and DSM data are cross-checked for CRS and spatial alignment.
          </div>

          <div style={{ display: "flex", gap: "12px", marginTop: "20px", alignItems: "center" }}>
            <button className="primary-button" style={{ flex: 1 }} disabled={!!stage || !file} onClick={analyze}>
              {stage && stage !== "Complete" ? `⏳ ${stage}…` : "🚀 Execute AI Pipeline & Open WebGIS"}
            </button>
            <button type="button" className="secondary-button" onClick={onBack} disabled={!!stage}>
              Cancel
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
